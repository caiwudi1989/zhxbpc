"""Library admission, project configuration and format-specific guidance."""
from pathlib import Path
import json

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QFormLayout, QLineEdit, QComboBox, QFileDialog, QToolButton, QLabel, QCheckBox,
    QPlainTextEdit, QTableWidget, QTableWidgetItem, QTextBrowser, QDialogButtonBox)

from pcide.core.libraries import (FORMATS, SYSTEM_LIBRARIES, load_libraries,
    save_libraries, import_library, plugin_catalog, calling_example)
from pcide.core.plugins import PluginManifest
from pcide.core.paths import read_json

GUIDE = '''<h2>加入支持库与模块</h2>
<p>“视图 → 当前操作提示”显示当前命令和页面的完整说明（Ctrl+Alt+H）。窗口菜单通过“设计 → 窗口菜单编辑器”或菜单栏属性页编辑，支持下级菜单、分隔线、快捷键、勾选和事件。单纯预览不执行脚本，F5/F4 运行才分发事件。</p>
<p>入口：左侧“支持库”→“加入”，或菜单“扩展”→“加入支持库/模块”。选择文件、填写代码名称和版本、选择公开接口，然后点“加入项目”。加入后在左侧双击命令插入调用，填写参数，再运行。</p>
<h3>系统支持库</h3><p>“配置”页选择本项目显示的系统库。中文源码项目按易语言核心库的分类方式展示 PCIDE 实际实现的流程、算术、文本、文件、数据库、网络等命令，以及窗口组件的属性、事件、方法和库常量。选中项即可查看说明与实际调用示例；双击或拖动插入示例。C/C++/C#/Unity/网页的示例位于左侧独立“代码片段”页。配置控制目录与补全；运行语言本身的内置函数仍可使用。</p>
<h3>源码模块 .py / .zhxb / .js / .ts</h3><p>文件复制到 src。导入页“公开接口”填写函数名，用逗号分隔；留空导出顶层函数。Python/中文模块在“模块引用表”维护精确版本、依赖和接口，用 模块名.函数(参数) 调用。Node 模块使用 require("./模块名").函数(参数)，路径相对当前源码；不同目录请修改路径。不同语言运行时不能直接混用。</p>
<h3>普通 DLL</h3><p>填写真实导出名、返回 ABI、调用约定；点击“编辑 DLL 参数”在表格填写名称、代码名称和参数 ABI。文件加入 resources/libraries，并建立 DLL 命令表声明；用代码名称(参数) 调用。DLL 由独立宿主加载。支持明确宽度标量及 utf8/utf16 文本输入；结构体、指针、输出参数与文本返回尚未开放。DLL 位数须匹配宿主。依赖 DLL 可通过资源导入加入同目录。</p>
<h3>封装包 .pcplugin / .zip / plugin.json</h3><p>包根放 plugin.json，声明 id/name/version/kind/entry/capabilities/permissions。目录形式选择 plugin.json，复制同目录入口与依赖；不要选择整个开发环境。kind 支持 python/native/dotnet/dex-remote，ABI 为 json-v1。Python 入口导出 plugin_entry(request)，从 request 的 capability/params 读取调用内容，返回可序列化结果。原生库导出 const char* pcide_call(const char* request_json)，.NET 入口是公开静态 string Call(string request_json)。调用：plugins.call("库ID", "能力", {参数})；返回实际结果。需要权限时明确勾选授权，未授权项显示“待授权”。每次调用关闭宿主；需要持久会话的库须使用协议封装。</p>
<h3>易模块 .ec / 易语言支持库 .fne</h3><p>可以加入项目保存，但显示“待桥接封装”。EC 在易语言“程序→易模块管理”引用，公开接口编译时合入；请用易语言编译成具有明确 ABI 的 DLL 后，按普通 DLL 加入，或由供应方提供独立桥接包。FNE 是易语言专用支持库，需易语言支持库 ABI 宿主或供应方封装；不能用普通 DLL 方式直接执行。PCIDE 尚无 EC 编译器或 FNE 专用宿主。</p>
<h3>DEX / PYD / .NET</h3><p>DEX 是 Android 字节码，先部署文件到 Android ART 宿主目录，填写 ws/wss 地址、宿主内相对路径、完整类名。类需 public static String call(String argument)。加入后生成 dex.call 示例；文件不自动上传，Android 真机调用待设备验收。PYD 用 Python 插件包装并声明 cp312 与位数；.NET 程序集通过 dotnet 插件封装，不能按普通 DLL 导出调用。</p>
<p>格式未知时请让提供方给出入口、调用协议、位数和依赖，并封装 plugin.json 后加入。</p>
<h3>参考资料</h3>
<p><a href="https://dywt.com.cn/help/zlsc/day/day1.htm">易语言支持库夹与菜单</a> · <a href="https://www.dywt.com.cn/help/zlsc/ecom.htm">易模块管理</a> · <a href="https://www.dywt.com.cn/gongneng/dsfzc.htm">第三方支持库接口</a> · <a href="https://learn.microsoft.com/en-us/dotnet/core/tutorials/creating-app-with-plugin-support">.NET 插件</a> · <a href="https://developer.android.com/reference/dalvik/system/DexClassLoader">Android DEX</a></p>'''


class LibraryDialog(QDialog):
    changed = Signal()

    def __init__(self, project, parent=None, page=0):
        super().__init__(parent)
        self.project=project
        self.setWindowTitle('支持库配置与模块管理')
        self.resize(900,700)
        layout=QVBoxLayout(self)
        self.tabs=QTabWidget()
        layout.addWidget(self.tabs)
        configuration=QWidget()
        config=QVBoxLayout(configuration)
        self.system_boxes={}
        model=load_libraries(project)
        for library in SYSTEM_LIBRARIES:
            box=QCheckBox(library['name'])
            box.setChecked(library['id'] in model['system'])
            self.system_boxes[library['id']]=box
            config.addWidget(box)
        save=QToolButton(text='保存系统支持库配置')
        save.clicked.connect(self.save_configuration)
        config.addWidget(save)
        config.addWidget(QLabel('已加入文件与独立宿主支持库：'))
        self.records=QTableWidget(0,4)
        self.records.setHorizontalHeaderLabels(['库/模块','格式','版本','状态'])
        self.records.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        config.addWidget(self.records)
        self.records.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.records.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        authorize=QToolButton(text='授权所选支持库声明的权限')
        authorize.clicked.connect(self.authorize_selected)
        config.addWidget(authorize)
        self.tabs.addTab(configuration,'配置')
        admission=QWidget()
        form=QFormLayout(admission)
        chooser=QHBoxLayout()
        self.source=QLineEdit()
        browse=QToolButton(text='选择文件…')
        browse.clicked.connect(self.choose_file)
        chooser.addWidget(self.source)
        chooser.addWidget(browse)
        form.addRow('模块/支持库文件',chooser)
        self.format_hint=QLabel('支持源码、EC、FNE、DLL、DEX、PYD 与 plugin.json 封装包')
        self.format_hint.setWordWrap(True)
        form.addRow(self.format_hint)
        self.source.textChanged.connect(self.update_format)
        self.identity=QLineEdit()
        self.version=QLineEdit('1.0.0')
        self.exports=QLineEdit()
        self.exports.setPlaceholderText('函数名用逗号分隔；留空导出顶层函数')
        form.addRow('代码名称',self.identity)
        form.addRow('版本',self.version)
        form.addRow('源码公开接口',self.exports)
        self.dll_entry=QLineEdit()
        self.dll_return=QComboBox()
        self.dll_return.addItems(['int32','uint8','uint32','int64','uint64','float32','float64','bool32','void'])
        self.convention=QComboBox()
        self.convention.addItems(['cdecl','stdcall','winapi'])
        self.parameters=QLineEdit('[]')
        self.parameters.setPlaceholderText('[{"id":"value","label":"数值","type":"int32"}]')
        self.parameter_button=QToolButton(text='编辑 DLL 参数（0 项）')
        self.parameter_button.clicked.connect(self.edit_dll_parameters)
        self.endpoint=QLineEdit('ws://127.0.0.1:8765')
        self.android_path=QLineEdit()
        self.class_name=QLineEdit()
        self.class_name.setPlaceholderText('pcide.android.ExampleDex')
        self.special=[]
        for label,widget,kind in [('DLL 导出名',self.dll_entry,'dll'),('DLL 返回 ABI',self.dll_return,'dll'),
            ('DLL 调用约定',self.convention,'dll'),('DLL 参数',self.parameter_button,'dll'),
            ('Android 桥接地址',self.endpoint,'dex'),('Android 宿主内路径',self.android_path,'dex'),('DEX 类名',self.class_name,'dex')]:
            form.addRow(label,widget)
            self.special.append((widget,form.labelForField(widget),kind))
        self.grant=QCheckBox('授权清单声明的权限（加入前请查看下方说明）')
        form.addRow(self.grant)
        self.permissions=QLabel()
        self.permissions.setWordWrap(True)
        form.addRow(self.permissions)
        join=QToolButton(text='加入项目并生成调用示例')
        join.clicked.connect(self.admit)
        form.addRow(join)
        self.example=QPlainTextEdit()
        self.example.setReadOnly(True)
        self.example.setMaximumHeight(110)
        form.addRow('调用示例',self.example)
        copy=QToolButton(text='复制调用示例')
        copy.clicked.connect(lambda: self.example.selectAll() or self.example.copy())
        form.addRow(copy)
        self.tabs.addTab(admission,'加入')
        help_view=QTextBrowser()
        help_view.setOpenExternalLinks(True)
        help_view.setHtml(GUIDE)
        self.tabs.addTab(help_view,'使用帮助')
        self.error=QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText('关闭')
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh()
        self.update_format()
        self.tabs.setCurrentIndex(page)

    def edit_dll_parameters(self):
        from pcide.ui.data_panel import DataPanel
        panel=DataPanel(self.project,self)
        panel.load({'apis':[{'id':'dll_command','label':'DLL 参数','entry':self.dll_entry.text() or 'entry',
                            'return_type':self.dll_return.currentText(),'parameters':json.loads(self.parameters.text())}]})
        panel.select_group('apis')
        panel.table.selectRow(0)
        def accepted(data):
            api=data['apis'][0]
            self.dll_entry.setText(api['entry'])
            self.parameters.setText(json.dumps(api['parameters'],ensure_ascii=False))
            self.parameter_button.setText('编辑 DLL 参数（'+str(len(api['parameters']))+' 项）')
        panel.changed.connect(accepted)
        panel._edit_members()
        panel.deleteLater()

    def refresh(self):
        rows=load_libraries(self.project)['imports']
        manifests=plugin_catalog(self.project)
        rows+= [{'id':m.id,'kind':m.kind,'version':m.version,'status':'待授权：'+','.join(sorted(set(m.permissions)-set(self.project.manifest.get('permissions',[])))) if set(m.permissions)-set(self.project.manifest.get('permissions',[])) else '独立宿主调用'} for m in manifests]
        self.record_data=rows
        self.records.setRowCount(len(rows))
        for row,record in enumerate(rows):
            for col,key in enumerate(('id','kind','version','status')):
                self.records.setItem(row,col,QTableWidgetItem(record.get(key,'')))
        self.records.resizeColumnsToContents()
        for column, width in enumerate((180, 100, 100, 340)):
            self.records.setColumnWidth(column, max(width, self.records.columnWidth(column)))

    def authorize_selected(self):
        row=self.records.currentRow()
        if row<0:
            self.error.setText('请先选择一个封装支持库；状态列列出了尚未授权的权限。')
            return
        identity=self.record_data[row]['id']
        manifest=next((m for m in plugin_catalog(self.project) if m.id==identity),None)
        if manifest is None:
            self.error.setText('此记录不是带权限清单的封装支持库。')
            return
        from pcide.core.paths import atomic_write_json
        self.project.manifest['permissions']=list(dict.fromkeys(self.project.manifest.get('permissions',[])+manifest.permissions))
        atomic_write_json(self.project.ide_dir/'project.json',self.project.manifest)
        self.error.setText('已授权 '+manifest.name+'：'+(', '.join(manifest.permissions) or '无权限要求'))
        self.refresh()
        self.changed.emit()

    def choose_file(self):
        file,_=QFileDialog.getOpenFileName(self,'加入支持库或模块','', '支持库与模块 ('+' '.join('*'+suffix for suffix in FORMATS)+');;所有文件 (*)')
        if file:
            self.source.setText(file)
            if not self.identity.text():
                self.identity.setText(Path(file).stem.replace('-','_').replace('.','_'))

    def update_format(self):
        suffix=Path(self.source.text()).suffix.lower()
        description=FORMATS.get(suffix,('选择支持库文件','未知格式请按使用帮助封装'))
        self.format_hint.setText(description[0]+'：'+description[1])
        for widget,label,kind in self.special:
            widget.setVisible(suffix=='.'+kind)
            label.setVisible(suffix=='.'+kind)
        self.exports.setEnabled(suffix in {'.py','.zhxb','.js','.ts'})
        self.grant.setVisible(suffix in {'.json','.zip','.pcplugin'})
        self.grant.setChecked(False)
        self.permissions.setText('')
        try:
            if suffix=='.json':
                manifest=PluginManifest.from_dict(read_json(self.source.text()))
            elif suffix in {'.zip','.pcplugin'}:
                import zipfile
                with zipfile.ZipFile(self.source.text()) as archive:
                    info=archive.getinfo('plugin.json')
                    if info.file_size>65536:
                        raise ValueError('清单过大')
                    manifest=PluginManifest.from_dict(json.loads(archive.read(info)))
            else:
                return
            self.permissions.setText('清单：'+manifest.name+'；独立宿主：'+manifest.kind+'；权限：'+(', '.join(manifest.permissions) or '无'))
        except Exception as exc:
            self.permissions.setText('清单读取失败：'+str(exc))

    def save_configuration(self):
        try:
            model=load_libraries(self.project)
            model['system']=[identity for identity,box in self.system_boxes.items() if box.isChecked()]
            save_libraries(self.project,model)
            self.changed.emit()
            self.error.setText('系统支持库配置已保存。')
        except (ValueError,OSError) as exc:
            self.error.setText(str(exc))

    def admit(self):
        try:
            record=import_library(self.project,self.source.text(),self.identity.text().strip(),version=self.version.text().strip(),
                exports=[v.strip() for v in self.exports.text().split(',') if v.strip()] or None,
                dll_entry=self.dll_entry.text().strip(),dll_return=self.dll_return.currentText(),
                calling_convention=self.convention.currentText(),parameters=json.loads(self.parameters.text()),
                endpoint=self.endpoint.text().strip(),android_path=self.android_path.text().strip(),class_name=self.class_name.text().strip(),grant=self.grant.isChecked())
            if record['kind'] in {'python','native','dotnet','dex-remote'}:
                record['capabilities']=next(m.capabilities for m in plugin_catalog(self.project) if m.id==record['id'])
            example=calling_example(record,self.project.manifest['language'])
            self.example.setPlainText(example or '此文件不能由当前语言直接调用，请查看“使用帮助”中的桥接/运行时说明。')
            self.error.setText(record['status']+'；文件：'+record['file'])
            self.changed.emit()
            self.refresh()
        except Exception as exc:
            self.error.setText('加入失败：'+str(exc))
