"""Source-backed parameters, separate from initialized local variables."""
import ast
import keyword
import re


def split_parameters(raw):
    result=[]
    start=0
    depth=0
    quote=''
    escaped=False
    for index,char in enumerate(raw):
        if quote:
            if escaped:
                escaped=False
            elif char=='\\':
                escaped=True
            elif char==quote:
                quote=''
        elif char in '\"\'`':
            quote=char
        elif char in '([{':
            depth+=1
        elif char in ')]}':
            depth-=1
        elif char==',' and depth==0:
            result.append(raw[start:index].strip())
            start=index+1
    result.append(raw[start:].strip())
    return [value for value in result if value]


def parameter_details(source, suffix, name):
    if suffix=='.py':
        node=next(node for node in ast.parse(source).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name)
        args=node.args
        positional=args.posonlyargs+args.args
        defaults=[None]*(len(positional)-len(args.defaults))+args.defaults
        records=[]
        def add(arg,default,kind):
            records.append({'name':arg.arg,'type':ast.unparse(arg.annotation) if arg.annotation else '',
                'default':ast.unparse(default) if default is not None else '', 'optional':default is not None,
                'kind':kind,'remark':''})
        for index,(arg,default) in enumerate(zip(positional,defaults)):
            add(arg,default,'posonly' if index<len(args.posonlyargs) else 'normal')
        if args.vararg:
            add(args.vararg,None,'rest')
        for arg,default in zip(args.kwonlyargs,args.kw_defaults):
            add(arg,default,'keyword')
        if args.kwarg:
            add(args.kwarg,None,'kwargs')
        return records
    if suffix=='.zhxb':
        from .compiler import parse
        procedure=next(p for p in parse(source).procedures if p.name==name)
        return [{**p,'optional':p.get('has_default',False),'kind':'normal'} for p in procedure.parameters]
    match=re.search(r'\bfunction\s+'+re.escape(name)+r'\s*\(',source)
    if not match:
        return []
    start=match.end()
    depth=1
    quote=''
    escaped=False
    end=start
    while end<len(source) and depth:
        char=source[end]
        if quote:
            if escaped:
                escaped=False
            elif char=='\\':
                escaped=True
            elif char==quote:
                quote=''
        elif char in '\"\'`':
            quote=char
        elif char=='(':
            depth+=1
        elif char==')':
            depth-=1
        end+=1
    result=[]
    for field in split_parameters(source[start:end-1]):
        head,separator,default=field.partition('=')
        identity,colon,typ=head.partition(':')
        identity=identity.strip()
        rest=identity.startswith('...')
        optional=identity.endswith('?') or bool(separator)
        identity=identity.removeprefix('...').removesuffix('?').strip()
        if not identity.isidentifier():
            raise ValueError('解构参数请在源码视图中编辑')
        result.append({'name':identity,'type':typ.strip() if colon else '', 'default':default.strip(),
                       'optional':optional,'kind':'rest' if rest else 'normal','remark':''})
    return result


def replace_parameters(source, suffix, name, parameters):
    names=[item['name'] for item in parameters]
    if len(names)>64 or len(names)!=len(set(names)) or any(not value.isidentifier() or keyword.iskeyword(value) for value in names):
        raise ValueError('参数名必须是唯一的合法标识符；最多64个参数')
    if suffix=='.zhxb':
        from .compiler import parse
        program=parse(source)
        procedure=next(p for p in program.procedures if p.name==name)
        if set(names)&{p['name'] for p in procedure.locals}:
            raise ValueError('参数与局部变量重名')
        lines=source.splitlines(keepends=True)
        declaration=lines[procedure.line-1]
        declaration=re.sub(r'(\.子程序\s+'+re.escape(name)+r')\s*\([^\n]*?\)',r'\1',declaration,count=1)
        lines[procedure.line-1]=declaration
        end=next((p.line-1 for p in program.procedures if p.line>procedure.line),len(lines))
        body=[line for line in lines[procedure.line:end] if not re.match(r'\s*\.参数\s',line)]
        declarations=[]
        for item in parameters:
            fields=[item['name'],item['type'] or '文本型']
            if item['optional']:
                fields.append(item['default'])
            declarations.append('.参数 '+', '.join(fields)+'\n')
        result=''.join(lines[:procedure.line]+declarations+body+lines[end:])
        parse(result)
        return result
    if suffix=='.py':
        node=next(node for node in ast.parse(source).body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==name)
        positional=[]
        keyword_only=[]
        vararg=None
        kwarg=None
        posonly=[]
        defaults=[]
        kwdefaults=[]
        optional_seen=False
        for item in parameters:
            arg=ast.arg(arg=item['name'],annotation=ast.parse(item['type'],mode='eval').body if item['type'] else None)
            default=ast.parse(item['default'],mode='eval').body if item['optional'] and item['default'] else None
            kind=item.get('kind','normal')
            if kind in {'normal','posonly'}:
                if item['optional'] and default is None:
                    raise ValueError('可省略参数必须填写默认值，例如 0、None 或 ""')
                if optional_seen and not item['optional']:
                    raise ValueError('必填位置参数必须放在可省略参数之前')
                optional_seen|=item['optional']
                (posonly if kind=='posonly' else positional).append(arg)
                if default is not None:
                    defaults.append(default)
            elif kind=='keyword':
                keyword_only.append(arg)
                kwdefaults.append(default)
            elif kind=='rest':
                if vararg:
                    raise ValueError('只能有一个 *args 参数')
                vararg=arg
            elif kind=='kwargs':
                if kwarg:
                    raise ValueError('只能有一个 **kwargs 参数')
                kwarg=arg
            else:
                raise ValueError('参数形式无效')
        args=ast.arguments(posonlyargs=posonly,args=positional,vararg=vararg,kwonlyargs=keyword_only,kw_defaults=kwdefaults,kwarg=kwarg,defaults=defaults)
        header=ast.unparse(args)
        lines=source.splitlines(keepends=True)
        offset=sum(len(line) for line in lines[:node.lineno-1])
        start=source.index('(',offset)+1
        # Tokenization prevents ')' in strings/default expressions ending the header.
        import io,tokenize
        tokens=list(tokenize.generate_tokens(io.StringIO(source[offset:]).readline))
        depth=0
        end=None
        for token in tokens:
            if token.type==tokenize.OP and token.string=='(':
                depth+=1
            elif token.type==tokenize.OP and token.string==')':
                depth-=1
                if depth==0:
                    end=offset+sum(len(line) for line in source[offset:].splitlines(keepends=True)[:token.start[0]-1])+token.start[1]
                    break
        result=source[:start]+header+source[end:]
        ast.parse(result)
        return result
    match=re.search(r'\bfunction\s+'+re.escape(name)+r'\s*\(',source)
    if not match:
        raise ValueError('子程序声明不存在')
    # Derive the exact end from the existing balanced parameter text.
    start=match.end()
    depth=1
    quote=''
    escaped=False
    end=start
    while end<len(source) and depth:
        char=source[end]
        if quote:
            if escaped: escaped=False
            elif char=='\\': escaped=True
            elif char==quote: quote=''
        elif char in '\"\'`': quote=char
        elif char=='(': depth+=1
        elif char==')': depth-=1
        end+=1
    fields=[]
    for item in parameters:
        field=('...' if item.get('kind')=='rest' else '')+item['name']
        if suffix=='.ts' and item['optional'] and not item['default']:
            field+='?'
        if suffix=='.ts' and item['type']:
            field+=': '+item['type']
        if item['optional'] and item['default']:
            field+=' = '+item['default']
        fields.append(field)
    return source[:start]+', '.join(fields)+source[end-1:]
