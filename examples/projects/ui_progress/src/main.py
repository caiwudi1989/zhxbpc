from pcide.runtime_api import ui, tasks
count = 0

def on_main_form_load(event=None):
    ui.set("Label1", text="后台进度已加载")

def on_Button1_click(event=None):
    global count
    count += 1
    ui.set("Label1", text=f"执行次数：{count}")
    with tasks.pool(workers=1,capacity=2) as pool:
        job=pool.submit(lambda cancel: ui.set("Demo",value=100))
        job.result(2)
