from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,
    QToolButton,QLabel,QDialogButtonBox,QComboBox)
from pcide.core.routine_signatures import parameter_details,replace_parameters
from pcide.core.libraries import TYPE_LABELS


class ParameterDialog(QDialog):
    def __init__(self,source,suffix,name,parent=None,notes=None,local_names=()):
        super().__init__(parent)
        self.source,self.suffix,self.name=source,suffix,name
        self.result_source=None
        self.notes={}
        self.local_names=set(local_names)
        self.setWindowTitle('子程序参数：'+name)
        self.resize(850,450)
        layout=QVBoxLayout(self)
        hint=QLabel('参数由调用方传入；默认值仅在可省略时使用。局部变量在子程序内部初始化。改参数名后请同步正文引用和调用处。')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['参数名','类型','默认值','可省略','参数形式','备注'])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        self.kinds=[]
        for item in parameter_details(source,suffix,name):
            self.add({**item,'remark':(notes or {}).get(item['name'],item.get('remark',''))})
        bar=QHBoxLayout()
        for label,callback in [('添加参数',lambda:self.add()),('删除参数',self.remove)]:
            button=QToolButton(text=label)
            button.clicked.connect(callback)
            bar.addWidget(button)
        bar.addStretch()
        layout.addLayout(bar)
        self.error=QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('确定')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('取消')
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add(self,item=None):
        item=item or {'name':'','type':'','default':'','optional':False,'kind':'normal','remark':''}
        row=self.table.rowCount()
        self.table.insertRow(row)
        for column,key in enumerate(['name','type','default','optional','kind','remark']):
            cell=QTableWidgetItem(str(item.get(key,'')))
            if key=='optional':
                cell.setText('')
                cell.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable)
                cell.setCheckState(Qt.CheckState.Checked if item.get(key) else Qt.CheckState.Unchecked)
            if key=='kind':
                cell.setData(Qt.ItemDataRole.UserRole,item.get('kind','normal'))
                cell.setText({'normal':'位置参数','posonly':'仅位置','keyword':'仅关键字','rest':'可变参数','kwargs':'关键字集合'}[item.get('kind','normal')])
                cell.setFlags(cell.flags()&~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row,column,cell)
        typ=QComboBox()
        typ.setEditable(True)
        typ.addItems(list(TYPE_LABELS) if self.suffix=='.zhxb' else ['','int','float','str','bool','list','dict','bytes'] if self.suffix=='.py' else ['','number','string','boolean','unknown[]','object'])
        typ.setCurrentText(item.get('type',''))
        self.table.setCellWidget(row,1,typ)
        for col,width in enumerate([140,120,150,70,100,180]):
            self.table.setColumnWidth(col,width)

    def remove(self):
        row=self.table.currentRow()
        if row>=0:
            self.table.removeRow(row)

    def save(self):
        try:
            parameters=[]
            for row in range(self.table.rowCount()):
                parameters.append({'name':self.table.item(row,0).text().strip(),'type':self.table.cellWidget(row,1).currentText().strip(),
                    'default':self.table.item(row,2).text(),'optional':self.table.item(row,3).checkState()==Qt.CheckState.Checked,
                    'kind':self.table.item(row,4).data(Qt.ItemDataRole.UserRole),'remark':self.table.item(row,5).text()})
            if self.local_names&{p['name'] for p in parameters}:
                raise ValueError('参数与局部变量重名')
            self.notes={p['name']:p['remark'] for p in parameters if p['remark']}
            self.result_source=replace_parameters(self.source,self.suffix,self.name,parameters)
            if self.suffix in {'.js','.ts'}:
                import uuid
                from pcide.core.paths import Paths,node_runtime
                from pcide.core.processes import run_bounded
                paths=Paths().ensure()
                temporary=paths.cache/('parameter-'+uuid.uuid4().hex+self.suffix)
                temporary.write_text(self.result_source,encoding='utf-8')
                checker='const fs=require("node:fs"),ts=require(process.argv[2]),p=process.argv[1];const f=ts.createSourceFile(p,fs.readFileSync(p,"utf8"),ts.ScriptTarget.Latest,true,p.endsWith(".ts")?ts.ScriptKind.TS:ts.ScriptKind.JS);if(f.parseDiagnostics.length)throw Error(ts.flattenDiagnosticMessageText(f.parseDiagnostics[0].messageText,"\\n"));'
                try:
                    run_bounded([node_runtime(),'-e',checker,str(temporary),str(paths.resources/'sdk/typescript/package/lib/typescript.js')],cwd=paths.root,timeout=10,log_path=paths.logs/'parameter-syntax.log')
                finally:
                    temporary.unlink()
            self.accept()
        except (ValueError,OSError,RuntimeError) as exc:
            self.error.setText('未保存：'+str(exc))
