"""Welcome, project factory, build settings and offline example UI."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox, QSplitter, QTextBrowser, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from pcide.core.development import TEMPLATES, TEMPLATE_MAP, TARGETS, TOOL_NAMES, validate_development
from pcide.core.examples import load_catalog
from pcide.core.paths import read_json
from pcide.core.toolchains import discover_tools, load_workspace_tools, save_workspace_tools

KINDS = {'script':'脚本与自动化','desktop':'桌面窗口软件','native':'原生工具与软件','managed':'C# 软件','web':'网页应用与小游戏','game':'游戏引擎工程'}
TOOL_LABELS={'python':'Python 解释器','node':'Node.js 运行时','cc':'C 编译器','cxx':'C++ 编译器',
             'cmake':'CMake 构建工具','dotnet':'.NET SDK','unity':'Unity 编辑器','godot':'Godot 编辑器'}

def dialog_buttons(flags):
    buttons=QDialogButtonBox(flags)
    for kind,text in [(QDialogButtonBox.StandardButton.Ok,'确定'),(QDialogButtonBox.StandardButton.Cancel,'取消'),
                      (QDialogButtonBox.StandardButton.Save,'保存'),(QDialogButtonBox.StandardButton.Close,'关闭')]:
        button=buttons.button(kind)
        if button:button.setText(text)
    return buttons

class ProjectChooser(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout=QFormLayout(self)
        self.name=QLineEdit('MySoftware')
        self.kind=QComboBox()
        for identity,label in KINDS.items(): self.kind.addItem(label,identity)
        self.template=QComboBox()
        self.target=QComboBox()
        self.description=QLabel()
        self.description.setWordWrap(True)
        layout.addRow('项目名称',self.name)
        layout.addRow('开发类型',self.kind)
        layout.addRow('语言 / 开发模式',self.template)
        layout.addRow('编译与发布方式',self.target)
        layout.addRow(self.description)
        self.kind.currentIndexChanged.connect(self.update_templates)
        self.template.currentIndexChanged.connect(self.update_targets)
        self.target.currentIndexChanged.connect(self.update_description)
        self.update_templates()

    def update_templates(self):
        self.template.blockSignals(True)
        self.template.clear()
        for item in TEMPLATES:
            if item.kind==self.kind.currentData(): self.template.addItem(item.label,item.id)
        self.template.blockSignals(False)
        self.update_targets()

    def update_targets(self):
        self.target.blockSignals(True)
        self.target.clear()
        item=TEMPLATE_MAP.get(self.template.currentData())
        if item:
            for identity in item.targets: self.target.addItem(TARGETS[identity][0],identity)
        self.target.blockSignals(False)
        self.update_description()

    def update_description(self):
        item=TEMPLATE_MAP.get(self.template.currentData())
        target=self.target.currentData()
        self.description.setText((item.description+'\n\n'+TARGETS[target][1]) if item and target else '')

    def selection(self):
        return self.name.text().strip(),self.template.currentData(),self.target.currentData()

class NewProjectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setWindowTitle('新建软件 / 游戏工程')
        self.resize(610,350)
        layout=QVBoxLayout(self)
        self.chooser=ProjectChooser(self)
        layout.addWidget(self.chooser)
        buttons=dialog_buttons(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

class WelcomePage(QWidget):
    createRequested=Signal(str,str,str)
    openRequested=Signal(str)
    examplesRequested=Signal()
    toolsRequested=Signal()
    def __init__(self,paths,parent=None):
        super().__init__(parent)
        self.paths=paths
        layout=QVBoxLayout(self)
        title=QLabel('PCIDE · 软件与游戏开发')
        title.setStyleSheet('font-size:26px;font-weight:600;padding:12px')
        layout.addWidget(title)
        layout.addWidget(QLabel('选择开发类型与模式，创建工程；修改后再次运行或增量构建即可继续迭代。'))
        self.chooser=ProjectChooser(self)
        layout.addWidget(self.chooser)
        row=QHBoxLayout()
        for text,callback in [('创建工程',lambda:self.createRequested.emit(*self.chooser.selection())),
                              ('100 个完整示例',self.examplesRequested.emit),('环境与引擎',self.toolsRequested.emit)]:
            button=QPushButton(text);button.clicked.connect(callback);row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel('最近使用 / 现有项目（双击载入）'))
        self.projects=QTreeWidget()
        self.projects.setHeaderLabels(['工程','语言 / 模式'])
        self.projects.setColumnWidth(0, 330)
        self.projects.itemDoubleClicked.connect(lambda item,_:self.openRequested.emit(item.data(0,Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.projects,1)
        self.refresh()

    def refresh(self):
        self.projects.clear()
        for path in sorted(self.paths.projects.glob('*/.pcide/project.json'))[:100]:
            raw=read_json(path,{})
            if isinstance(raw,dict):
                item=QTreeWidgetItem(self.projects,[raw.get('name',path.parents[1].name),raw.get('language','')+' / '+raw.get('development',{}).get('template','脚本')])
                item.setData(0,Qt.ItemDataRole.UserRole,str(path.parents[1]))

class BuildDialog(QDialog):
    def __init__(self,project,paths,parent=None):
        super().__init__(parent)
        from pcide.core.build_service import BuildService
        from pcide.core.development import template_for
        self.project=project
        self.setWindowTitle('编译 / 静态编译 / 发布')
        self.resize(680,410)
        root=QVBoxLayout(self);form=QFormLayout()
        self.target=QComboBox()
        for identity in template_for(project).targets:self.target.addItem(TARGETS[identity][0],identity)
        self.target.setCurrentIndex(self.target.findData(project.manifest['development']['target']))
        self.configuration=QComboBox();self.configuration.addItems(['Release','Debug'])
        self.configuration.setCurrentText(project.manifest['development']['configuration'])
        self.jobs=QSpinBox();self.jobs.setRange(1,4);self.jobs.setValue(project.manifest['development']['jobs'])
        form.addRow('构建方式',self.target);form.addRow('配置',self.configuration);form.addRow('并行上限',self.jobs)
        root.addLayout(form)
        self.description=QLabel();self.description.setWordWrap(True)
        def refresh():
            desired=self.configuration.currentText()
            self.configuration.clear()
            self.configuration.addItems(['Release'] if self.target.currentData() in {'script-standalone','script-system','web','unity'} else ['Release','Debug'])
            if self.configuration.findText(desired)>=0:self.configuration.setCurrentText(desired)
            info=BuildService(paths).describe(project,self.target.currentData())
            self.description.setText(info['description']+'\n\n输出：'+info['output']+'\n\n'
                '普通编译复用缓存；重新构建重新执行编译。工具输出、耗时、体积和缓存命中会显示在输出区。\n'
                '环境缺失会报告需要的已安装工具；此入口不下载环境或依赖。')
        self.target.currentIndexChanged.connect(refresh);refresh();root.addWidget(self.description,1)
        self.force=False
        buttons=dialog_buttons(QDialogButtonBox.StandardButton.Cancel)
        normal=buttons.addButton('增量编译',QDialogButtonBox.ButtonRole.AcceptRole)
        rebuild=buttons.addButton('重新构建',QDialogButtonBox.ButtonRole.ActionRole)
        normal.clicked.connect(self.accept)
        rebuild.clicked.connect(self.rebuild)
        buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def rebuild(self):self.force=True;self.accept()

    def settings(self):
        dev=dict(self.project.manifest['development'])
        dev.update(target=self.target.currentData(),configuration=self.configuration.currentText(),jobs=self.jobs.value())
        return validate_development(dev,self.project.manifest['language'])

class ToolsDialog(QDialog):
    def __init__(self,project,parent=None,paths=None):
        super().__init__(parent)
        from pcide.core.paths import Paths
        self.paths=paths or getattr(parent,'paths',None) or Paths()
        self.project=project
        self.setWindowTitle('系统环境与游戏引擎（只配置已有工具）')
        self.resize(850,570)
        root=QVBoxLayout(self)
        root.addWidget(QLabel('自动发现系统 PATH / 安装目录，也可填写已安装的 .exe。留空继续使用系统发现结果。'))
        form=QFormLayout();self.fields={}
        defaults=load_workspace_tools(self.paths)
        records=discover_tools(project,self.paths)
        for name in TOOL_NAMES:
            row=QWidget();line=QHBoxLayout(row);line.setContentsMargins(0,0,0,0)
            field=QLineEdit(project.manifest['development']['tools'].get(name,defaults.get(name,'')))
            field.setPlaceholderText(records[name]['path'] or '未发现；可稍后安装再配置')
            browse=QPushButton('选择')
            def choose(_,entry=field):
                from PySide6.QtWidgets import QFileDialog
                value,_=QFileDialog.getOpenFileName(self,'选择已有工具',entry.text(),'程序 (*.exe)')
                if value:entry.setText(value)
            browse.clicked.connect(choose)
            line.addWidget(field,1);line.addWidget(browse);line.addWidget(QLabel('可用' if records[name]['available'] else '未配置'))
            form.addRow(TOOL_LABELS[name],row);self.fields[name]=field
        engine_row=QWidget();engine_layout=QHBoxLayout(engine_row);engine_layout.setContentsMargins(0,0,0,0)
        self.engine_root=QLineEdit(project.manifest['development'].get('engine_root',''))
        self.engine_root.setPlaceholderText('引擎模板留空使用当前工程；可绑定现有Unity/Godot工程的完整路径')
        browse_engine=QPushButton('选择工程')
        def choose_engine():
            from PySide6.QtWidgets import QFileDialog
            value=QFileDialog.getExistingDirectory(self,'选择已有Unity/Godot工程',self.engine_root.text())
            if value:self.engine_root.setText(value)
        browse_engine.clicked.connect(choose_engine)
        engine_layout.addWidget(self.engine_root,1);engine_layout.addWidget(browse_engine)
        engine_row.setEnabled(TEMPLATE_MAP[project.manifest['development']['template']].mode=='engine')
        form.addRow('外部引擎工程',engine_row)
        root.addLayout(form)
        self.shared=QCheckBox('将工具路径保存为工作区默认，供新工程和示例副本复用')
        self.shared.setChecked(True);root.addWidget(self.shared)
        info=QTextBrowser();info.setOpenExternalLinks(True)
        info.setHtml('Unity：编辑器与Windows Build Support；首次导入/许可证由Unity管理。<br>'
                     'Godot：Godot 4编辑器与Windows导出模板。<br>C/C++：PATH中的MinGW/Clang，或已初始化的MSVC开发命令环境。<br>'
                     '.NET：已安装SDK/目标框架；发布禁用远程NuGet源。Native AOT需要本机已有原生工具和包。<br>'
                     '<a href="https://docs.unity3d.com/Manual/EditorCommandLineArguments.html">Unity官方命令行</a> · '
                     '<a href="https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html">Godot官方命令行</a>')
        root.addWidget(info,1)
        self.error=QLabel();root.addWidget(self.error)
        buttons=dialog_buttons(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);root.addWidget(buttons)

    def save(self):
        try:
            dev=dict(self.project.manifest['development'])
            dev['tools']={key:field.text().strip() for key,field in self.fields.items() if field.text().strip()}
            dev['engine_root']=self.engine_root.text().strip()
            dev=validate_development(dev,self.project.manifest['language'])
            for path in dev['tools'].values():
                if not Path(path).is_file():raise ValueError('工具不存在：'+path)
            if dev['engine_root']:
                from pcide.core.project import Project
                from pcide.core.engines import engine_root
                candidate=Project(self.project.root,{**self.project.manifest,'development':dev})
                engine_root(candidate)
            self.project.manifest['development']=dev;self.project.save_manifest()
            if self.shared.isChecked():save_workspace_tools(self.paths,dev['tools'])
            self.accept()
        except (ValueError,OSError) as exc:self.error.setText(str(exc))

class ExampleDialog(QDialog):
    def __init__(self,paths,parent=None):
        super().__init__(parent)
        self.setWindowTitle('完整示例中心 · 双击载入可编辑副本')
        self.resize(1050,670)
        self.root,self.catalog=load_catalog(paths)
        self.selected_example=None
        root=QVBoxLayout(self)
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('搜索名称、功能、语言或说明')
        self.category=QComboBox();self.category.addItem('全部类别','')
        for category in sorted({item['category'] for item in self.catalog}):self.category.addItem(category,category)
        row.addWidget(self.category);row.addWidget(self.search,1);root.addLayout(row)
        split=QSplitter();self.tree=QTreeWidget();self.tree.setHeaderLabels(['示例','模板']);self.tree.setColumnWidth(0,240)
        self.details=QTextBrowser();split.addWidget(self.tree);split.addWidget(self.details);split.setSizes([460,550]);root.addWidget(split,1)
        self.count=QLabel();root.addWidget(self.count)
        self.search.textChanged.connect(self.populate);self.category.currentIndexChanged.connect(self.populate)
        self.tree.currentItemChanged.connect(self.inspect)
        self.tree.itemDoubleClicked.connect(lambda *_:self.load())
        buttons=dialog_buttons(QDialogButtonBox.StandardButton.Close)
        load=buttons.addButton('载入示例副本',QDialogButtonBox.ButtonRole.AcceptRole)
        load.clicked.connect(self.load);buttons.rejected.connect(self.reject);root.addWidget(buttons);self.populate()

    def populate(self,*_):
        self.tree.clear();query=self.search.text().casefold().strip();category=self.category.currentData()
        for item in self.catalog:
            if category and item['category']!=category:continue
            if query and query not in ' '.join(str(v) for v in item.values()).casefold():continue
            row=QTreeWidgetItem(self.tree,[item['title'],TEMPLATE_MAP[item['template']].label]);row.setData(0,Qt.ItemDataRole.UserRole,item)
        self.count.setText(f'显示 {self.tree.topLevelItemCount()} / {len(self.catalog)} 个完整工程')
        if self.tree.topLevelItemCount():self.tree.setCurrentItem(self.tree.topLevelItem(0))
        else:self.details.clear()

    def inspect(self,item,*_):
        if item:
            record=item.data(0,Qt.ItemDataRole.UserRole)
            self.details.setMarkdown((self.root/record['path']/'README.md').read_text(encoding='utf-8'))

    def load(self):
        item=self.tree.currentItem()
        if item:self.selected_example=item.data(0,Qt.ItemDataRole.UserRole);self.accept()
