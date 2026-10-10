import ast
import unittest
from pcide.core.compiler import emit_python
from pcide.core.routine_signatures import parameter_details,replace_parameters
from pcide.core.routines import scan


class ParameterTests(unittest.TestCase):
    def test_python_signature_keeps_required_defaults_keyword_only_and_body(self):
        source='def work(value: int, options=(1, 2), *, enabled=True):\n    local = value + 1\n    return local\n'
        parameters=parameter_details(source,'.py','work')
        self.assertFalse(parameters[0]['optional'])
        self.assertTrue(parameters[1]['optional'])
        self.assertEqual(parameters[2]['kind'],'keyword')
        parameters[1]['default']='(3, 4)'
        updated=replace_parameters(source,'.py','work',parameters)
        self.assertIn('local = value + 1',updated)
        namespace={}
        exec(updated,namespace)
        self.assertEqual(namespace['work'](2),3)
        with self.assertRaises(TypeError):
            namespace['work']()

    def test_chinese_parameters_are_input_and_locals_reset_each_call(self):
        source='.版本 2\n.子程序 work, 整数型\n.参数 value, 整数型\n.局部变量 local, 整数型, 1\n返回(value + local)\n'
        namespace={}
        exec(emit_python(source),namespace)
        self.assertEqual(namespace['work'](5),6)
        self.assertEqual(namespace['work'](5),6)
        with self.assertRaises(TypeError):
            namespace['work']()
        parameters=parameter_details(source,'.zhxb','work')
        self.assertEqual([p['name'] for p in parameters],['value'])
        self.assertFalse(parameters[0]['optional'])
        parameters[0].update(optional=True,default='4')
        updated=replace_parameters(source,'.zhxb','work',parameters)
        self.assertIn('.局部变量 local',updated)
        exec(emit_python(updated),namespace)
        self.assertEqual(namespace['work'](),5)
        self.assertEqual(scan(updated,'.zhxb')[0]['parameters'],['value'])

    def test_node_parameter_arrays_and_source_body_are_preserved(self):
        for suffix in ['.js','.ts']:
            source='function work(value'+(': number' if suffix=='.ts' else '')+', options = [1, 2]) { return value; }'
            params=parameter_details(source,suffix,'work')
            self.assertEqual([p['name'] for p in params],['value','options'])
            self.assertEqual(scan(source,suffix)[0]['parameters'],['value','options'])
            params[1]['default']='[3, 4]'
            self.assertIn('return value;',replace_parameters(source,suffix,'work',params))

    def test_duplicate_names_and_required_after_optional_are_rejected(self):
        source='def work(value):\n    return value\n'
        params=parameter_details(source,'.py','work')
        with self.assertRaises(ValueError):
            replace_parameters(source,'.py','work',params+params)
        with self.assertRaises(ValueError):
            emit_python('.版本 2\n.子程序 work\n.参数 a, 整数型, 1\n.参数 b, 整数型\n返回(a)\n')

    def test_variadic_parameters_shadow_global_data(self):
        from pcide.core.source import compile_source,check_value
        from types import SimpleNamespace
        source='def work(*args, **kwargs):\n    return args[0] + kwargs["value"]\n'
        code=compile_source(source,'main.py',data={'variables':[{'id':'args','scope':'global'}],'constants':[],'types':[]})
        namespace={'__pcide_data__':SimpleNamespace(args=999),'__pcide_check_value__':check_value}
        exec(code,namespace)
        self.assertEqual(namespace['work'](20,value=22),42)
        self.assertEqual(scan(source,'.py')[0]['parameters'],['args','kwargs'])
