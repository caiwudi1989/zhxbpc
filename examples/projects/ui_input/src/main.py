from pcide.runtime_api import ui, tasks
count = 0

def on_main_form_load(event=None):
    ui.set("Label1", text="文本输入已加载")

def on_Button1_click(event=None):
    global count
    count += 1
    ui.set("Label1", text=f"执行次数：{count}")
