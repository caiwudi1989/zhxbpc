"""Build 100 distinct, documented source projects from the shared factory. No downloads."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'src'))
from pcide.core.development import create_project
from pcide.core.paths import Paths, atomic_write_json
from pcide.core.project import ControlModel, DEFAULT_FORM

# id, title, subject, source, observable result
PYTHON = [
 ('text_unicode','Unicode 文本','文本','text="PC软件🙂"\nprint(len(text), text.upper())\n','5 PC软件🙂'),
 ('text_regex','正则提取','文本','import re\nprint(re.findall(r"\\d+", "订单12和34"))\n',"['12', '34']"),
 ('text_template','文本模板','文本','from string import Template\nprint(Template("欢迎 $name").substitute(name="开发者"))\n','欢迎 开发者'),
 ('text_counter','词频统计','文本','from collections import Counter\nprint(Counter("red blue red".split()).most_common())\n',"[('red', 2), ('blue', 1)]"),
 ('text_normalize','Unicode 规范化','文本','import unicodedata\nprint(unicodedata.normalize("NFKC", "ＡＢＣ１２３"))\n','ABC123'),
 ('text_diff','源码差异','文本','import difflib\nprint("".join(difflib.unified_diff(["old\\n"], ["new\\n"], fromfile="v1", tofile="v2")))\n','显示old/new行差异'),
 ('data_json','JSON 保存与读取','数据','import json\nfrom pathlib import Path\np=Path("resources/data.json")\np.write_text(json.dumps({"名字":"软件","版本":1},ensure_ascii=False),encoding="utf-8")\nprint(json.loads(p.read_text(encoding="utf-8")))\n',"{'名字': '软件', '版本': 1}"),
 ('data_csv','CSV 报表','数据','import csv,io\ns=io.StringIO()\nw=csv.writer(s)\nw.writerows([["name","score"],["Alice",95]])\nprint(list(csv.DictReader(io.StringIO(s.getvalue()))))\n',"[{'name': 'Alice', 'score': '95'}]"),
 ('data_ini','INI 设置','数据','import configparser,io\nc=configparser.ConfigParser()\nc.read_string("[app]\\nwidth=640\\n")\nprint(c.getint("app","width"))\n','640'),
 ('data_xml','XML 解析','数据','import xml.etree.ElementTree as ET\nnode=ET.fromstring("<app><title>PCIDE</title></app>")\nprint(node.findtext("title"))\n','PCIDE'),
 ('data_dataclass','数据类','数据','from dataclasses import dataclass,asdict\n@dataclass\nclass Item:\n    name: str\n    price: int\nprint(asdict(Item("book",20)))\n',"{'name': 'book', 'price': 20}"),
 ('data_validate','输入校验','数据','def validate(value):\n    if not isinstance(value,int) or isinstance(value,bool) or not 0<=value<=100:\n        raise ValueError("范围应为0..100")\n    return value\nprint(validate(42))\ntry:\n    validate(101)\nexcept ValueError as exc:\n    print(exc)\n','42及范围错误'),
 ('file_atomic','原子文件替换','文件','from pathlib import Path\nimport os\np=Path("resources/settings.txt")\nt=p.with_suffix(".tmp")\ntry:\n    t.write_text("version=2",encoding="utf-8")\n    os.replace(t,p)\n    print(p.read_text(encoding="utf-8"))\nfinally:\n    t.unlink(missing_ok=True)\n','version=2，无残留.tmp'),
 ('file_paths','相对路径校验','文件','from pathlib import Path\ndef safe_path(name):\n    base=Path("resources").resolve()\n    target=(base/name).resolve()\n    if not target.is_relative_to(base):\n        raise ValueError("路径越界")\n    return target.name\nprint(safe_path("data.txt"))\ntry:\n    safe_path("../../escape")\nexcept ValueError as exc:\n    print(exc)\n','data.txt及路径越界'),
 ('file_hash','文件 SHA256','文件','import hashlib\nfrom pathlib import Path\np=Path("resources/hash.txt")\np.write_bytes(b"abc")\nh=hashlib.sha256()\nwith p.open("rb") as f:\n    for block in iter(lambda:f.read(8192),b""):\n        h.update(block)\nprint(h.hexdigest())\n','ba7816bf…15ad'),
 ('file_zip','ZIP 资源归档','文件','from pathlib import Path\nfrom zipfile import ZipFile\np=Path("resources/sample.zip")\nwith ZipFile(p,"w") as z:\n    z.writestr("readme.txt","hello")\nwith ZipFile(p) as z:\n    print(z.read("readme.txt").decode())\n','hello；自动关闭ZIP'),
 ('file_temp','临时目录自动回收','文件','from contextlib import contextmanager\nfrom pathlib import Path\nimport shutil,uuid\n@contextmanager\ndef temporary_directory():\n    root=Path("resources").resolve()\n    directory=root/("temp-"+uuid.uuid4().hex)\n    directory.mkdir()\n    try: yield directory\n    finally:\n        if directory.resolve().is_relative_to(root): shutil.rmtree(directory)\nwith temporary_directory() as directory:\n    file=directory/"demo.txt"\n    file.write_text("temporary",encoding="utf-8")\n    print(file.read_text(encoding="utf-8"))\nprint("reclaimed",not directory.exists())\n','temporary / reclaimed True'),
 ('file_walk','有界目录扫描','文件','from pathlib import Path\nfiles=[]\nfor p in Path("src").rglob("*"):\n    if p.is_file(): files.append(p.name)\n    if len(files)>=100: break\nprint(sorted(files))\n',"['main.py']"),
 ('db_crud','SQLite 增删改查','数据库','import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect(":memory:")) as db:\n    db.execute("create table items(id integer primary key,name text)")\n    db.execute("insert into items(name) values(?)",("old",))\n    db.execute("update items set name=? where id=?",("new",1))\n    print(db.execute("select * from items").fetchall())\n    db.execute("delete from items where id=?",(1,))\n    print(db.execute("select count(*) from items").fetchone()[0])\n',"[(1, 'new')] / 0"),
 ('db_transaction','事务回滚','数据库','import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect(":memory:")) as db:\n    db.execute("create table items(id integer)")\n    try:\n        with db:\n            db.execute("insert into items values(1)")\n            raise ValueError("rollback")\n    except ValueError:\n        pass\n    print(db.execute("select count(*) from items").fetchone()[0])\n','0'),
 ('db_parameter','SQL 参数绑定','数据库','import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect(":memory:")) as db:\n    db.execute("create table notes(text)")\n    db.execute("insert into notes values(?)",("a\'b",))\n    print(db.execute("select text from notes").fetchone()[0])\n',"a'b"),
 ('db_migration','数据库版本迁移','数据库','import sqlite3\nfrom contextlib import closing\nwith closing(sqlite3.connect(":memory:")) as db:\n    version=db.execute("pragma user_version").fetchone()[0]\n    if version<1:\n        with db:\n            db.execute("create table users(id integer,name text)")\n            db.execute("pragma user_version=1")\n    print(db.execute("pragma user_version").fetchone()[0])\n','1'),
 ('algo_sort','稳定排序','算法','rows=[("Amy",2),("Bob",1),("Cal",2)]\nprint(sorted(rows,key=lambda r:r[1]))\n',"Bob优先，Amy和Cal顺序保持"),
 ('algo_bisect','二分查找','算法','from bisect import bisect_left\nitems=[1,3,5,7]\nprint(bisect_left(items,5),bisect_left(items,4))\n','2 2'),
 ('algo_heap','优先队列','算法','import heapq\nq=[]\nfor priority,name in [(3,"low"),(1,"high"),(2,"normal")]:\n    heapq.heappush(q,(priority,name))\nwhile q:\n    print(heapq.heappop(q)[1])\n','high / normal / low'),
 ('algo_bfs','广度优先搜索','算法','from collections import deque\ngraph={"A":["B","C"],"B":["D"],"C":[],"D":[]}\nq=deque(["A"]); seen={"A"}; result=[]\nwhile q:\n    node=q.popleft(); result.append(node)\n    for child in graph[node]:\n        if child not in seen:\n            seen.add(child); q.append(child)\nprint(result)\n',"['A', 'B', 'C', 'D']"),
 ('algo_cache','有界 LRU 缓存','算法','from functools import lru_cache\n@lru_cache(maxsize=8)\ndef square(value):\n    return value*value\nprint(square(4),square(4),square.cache_info().hits)\nsquare.cache_clear()\n','16 16 1'),
 ('algo_generator','流式生成器','算法','def batches(items,size):\n    batch=[]\n    for item in items:\n        batch.append(item)\n        if len(batch)==size:\n            yield batch; batch=[]\n    if batch: yield batch\nprint(list(batches(range(7),3)))\n',"[[0, 1, 2], [3, 4, 5], [6]]"),
 ('math_decimal','金额精度','数学','from decimal import Decimal,ROUND_HALF_UP\namount=(Decimal("0.1")+Decimal("0.2")).quantize(Decimal("0.00"),rounding=ROUND_HALF_UP)\nprint(amount)\n','0.30'),
 ('math_statistics','统计摘要','数学','from statistics import mean,median,pstdev\nvalues=[2,4,6,8]\nprint(mean(values),median(values),round(pstdev(values),3))\n','5 5.0 2.236'),
 ('math_vector','二维向量','游戏基础','import math\na=(3,4)\nlength=math.hypot(*a)\nprint(length,tuple(x/length for x in a))\n','5.0 (0.6, 0.8)'),
 ('math_collision','矩形碰撞','游戏基础','def overlap(a,b):\n    return a[0]<b[0]+b[2] and a[0]+a[2]>b[0] and a[1]<b[1]+b[3] and a[1]+a[3]>b[1]\nprint(overlap((0,0,10,10),(5,5,10,10)),overlap((0,0,10,10),(20,20,2,2)))\n','True False'),
 ('design_factory','工厂注册与复用','工程模式','class Factory:\n    def __init__(self): self.builders={}\n    def register(self,key,builder):\n        if key in self.builders: raise ValueError("重复类型")\n        self.builders[key]=builder\n    def create(self,key,**config): return self.builders[key](**config)\nf=Factory()\nf.register("label",lambda text:{"type":"Label","text":text})\nprint(f.create("label",text="ready"))\n',"{'type': 'Label', 'text': 'ready'}"),
 ('design_strategy','策略切换','工程模式','strategies={"upper":str.upper,"lower":str.lower}\ndef process(text,mode):\n    if mode not in strategies: raise ValueError("unsupported")\n    return strategies[mode](text)\nprint(process("Hello","upper"),process("Hello","lower"))\n','HELLO hello'),
 ('design_state','状态机','工程模式','class Machine:\n    transitions={("idle","start"):"running",("running","stop"):"idle"}\n    def __init__(self): self.state="idle"\n    def send(self,event): self.state=self.transitions[(self.state,event)]\nm=Machine(); m.send("start"); print(m.state); m.send("stop"); print(m.state)\n','running / idle'),
 ('design_command','命令与撤销','工程模式','class Add:\n    def __init__(self,items,value): self.items,self.value=items,value\n    def execute(self): self.items.append(self.value)\n    def undo(self): self.items.pop()\nitems=[]; cmd=Add(items,42); cmd.execute(); print(items); cmd.undo(); print(items)\n','[42] / []'),
 ('design_observer','订阅与解除','工程模式','class Events:\n    def __init__(self): self.listeners=[]\n    def subscribe(self,fn): self.listeners.append(fn)\n    def emit(self,value):\n        for fn in tuple(self.listeners): fn(value)\n    def unsubscribe(self,fn): self.listeners.remove(fn)\ne=Events(); e.subscribe(print); e.emit("once"); e.unsubscribe(print); e.emit("silent")\n','只输出once'),
 ('design_repository','存储接口','工程模式','class Repository:\n    def __init__(self): self.data={}\n    def put(self,key,value): self.data[key]=value\n    def get(self,key): return self.data[key]\nr=Repository(); r.put("name","PCIDE"); print(r.get("name"))\n','PCIDE'),
 ('task_pool','有界后台任务池','线程','from pcide.runtime_api import tasks\nwith tasks.pool(workers=2,capacity=4) as p:\n    jobs=[p.submit(lambda cancel,n:n*n,n) for n in range(4)]\n    print([j.result(5) for j in jobs])\n','[0, 1, 4, 9]；退出回收线程'),
 ('task_cancel','协作取消任务','线程','from pcide.runtime_api import tasks\nimport threading\nstarted=threading.Event()\ndef work(cancel):\n    started.set()\n    while tasks.sleep(cancel,0.01): pass\n    return "cancelled"\nwith tasks.pool(workers=1,capacity=2) as p:\n    job=p.submit(work)\n    started.wait(2); job.cancel()\n    print(job.result(2))\n','cancelled'),
 ('task_error','任务异常传递','线程','from pcide.runtime_api import tasks\ndef work(cancel): raise ValueError("task failed")\nwith tasks.pool(workers=1,capacity=2) as p:\n    job=p.submit(work)\n    try: job.result(2)\n    except ValueError as exc: print(exc)\n','task failed'),
 ('task_lock','共享计数与互斥','线程','from pcide.runtime_api import tasks\nimport threading\nlock=threading.Lock(); values=[]\ndef work(cancel,n):\n    with lock: values.append(n)\nwith tasks.pool(workers=2,capacity=4) as p:\n    jobs=[p.submit(work,n) for n in range(4)]\n    for job in jobs: job.result(2)\nprint(sorted(values))\n','[0, 1, 2, 3]'),
 ('task_queue','生产消费队列','线程','from pcide.runtime_api import tasks\nimport queue\nq=queue.Queue(maxsize=4)\ndef produce(cancel):\n    for n in range(3): q.put(n,timeout=1)\n    q.put(None,timeout=1)\ndef consume(cancel):\n    values=[]\n    while not cancel.is_set():\n        item=q.get(timeout=1)\n        if item is None: return values\n        values.append(item)\nwith tasks.pool(workers=2,capacity=4) as p:\n    producer=p.submit(produce); consumer=p.submit(consume)\n    producer.result(2); print(consumer.result(2))\n','[0, 1, 2]'),
 ('task_capacity','任务容量限制','线程','from pcide.runtime_api import tasks\nimport threading\nstarted=threading.Event()\ndef work(cancel):\n    started.set(); cancel.wait(2)\nwith tasks.pool(workers=1,capacity=1) as p:\n    job=p.submit(work); started.wait(1)\n    try: p.submit(work)\n    except RuntimeError as exc: print(exc)\n    job.cancel(); job.result(2)\n','报告任务容量已满，退出回收'),
 ('task_event','线程事件同步','线程','from pcide.runtime_api import tasks\nimport threading\nready=threading.Event()\ndef work(cancel): ready.set(); return 42\nwith tasks.pool(workers=1,capacity=2) as p:\n    job=p.submit(work)\n    print(ready.wait(2),job.result(2))\n','True 42'),
 ('task_deadline','等待超时与取消','线程','from pcide.runtime_api import tasks\nfrom concurrent.futures import TimeoutError\nimport threading\nstarted=threading.Event()\ndef work(cancel): started.set(); cancel.wait(2); return "stopped"\nwith tasks.pool(workers=1,capacity=2) as p:\n    job=p.submit(work); started.wait(1)\n    try: job.result(0.01)\n    except TimeoutError: print("timeout"); job.cancel()\n    print(job.result(2))\n','timeout / stopped'),
 ('resource_context','自定义资源上下文','资源管理','from contextlib import contextmanager\n@contextmanager\ndef resource():\n    print("open")\n    try: yield "data"\n    finally: print("close")\nwith resource() as value: print(value)\n','open / data / close'),
 ('resource_exitstack','多资源自动关闭','资源管理','from contextlib import ExitStack\nfrom pathlib import Path\nfor name in ["a","b"]: Path("resources/"+name+".txt").write_text(name,encoding="utf-8")\nwith ExitStack() as stack:\n    files=[stack.enter_context(open("resources/"+n+".txt",encoding="utf-8")) for n in ["a","b"]]\n    print([f.read() for f in files])\nprint(all(f.closed for f in files))\n',"['a', 'b'] / True"),
 ('resource_weakref','弱引用缓存','资源管理','import weakref,gc\nclass Item: pass\ncache=weakref.WeakValueDictionary()\nitem=Item(); cache["id"]=item\nprint(len(cache)); del item; gc.collect(); print(len(cache))\n','1 / 0'),
 ('resource_memory','临时内存测量','资源管理','import tracemalloc\ntracemalloc.start()\ndata=bytearray(100000)\nprint("allocated",tracemalloc.get_traced_memory()[0]>90000)\ndel data\nprint("released",tracemalloc.get_traced_memory()[0]<90000)\ntracemalloc.stop()\n','allocated True / released True（逻辑分配统计）'),
 ('time_datetime','日期与时区','时间','from datetime import datetime,timezone,timedelta\nt=datetime(2026,1,1,tzinfo=timezone.utc)\nprint(t.astimezone(timezone(timedelta(hours=8))).isoformat())\n','2026-01-01T08:00:00+08:00'),
 ('time_monotonic','耗时测量','时间','import time\nstart=time.perf_counter()\nvalue=sum(range(10000))\nprint(value,"elapsed_nonnegative",time.perf_counter()-start>=0)\n','49995000 elapsed_nonnegative True'),
 ('network_url','URL 参数编码','网络','from urllib.parse import urlencode,urlparse,parse_qs\nurl="https://example.invalid/search?"+urlencode({"q":"PC 软件"})\nprint(parse_qs(urlparse(url).query))\n',"{'q': ['PC 软件']}，无网络请求"),
 ('network_http','离线 HTTP 请求解析','网络','from email.parser import Parser\nrequest="GET /health HTTP/1.1\\r\\nHost: localhost\\r\\nAccept: application/json\\r\\n\\r\\n"\nline,headers=request.split("\\r\\n",1)\nprint(line,Parser().parsestr(headers)["Host"])\n','GET /health HTTP/1.1 localhost'),
 ('pc_environment','系统环境信息','PC功能','import os,platform\nprint(platform.system(),platform.machine())\nprint("cpu_count",os.cpu_count())\n','显示实际系统与CPU数量'),
 ('pc_windows','枚举 Windows 窗口','PC功能','from pcide.runtime_api import list_windows\nwindows=list_windows()\nprint("window_count",len(windows))\nfor window in windows[:5]: print(window["title"])\n','列出本机窗口；需要Windows'),
 ('binary_struct','二进制结构','数据','import struct\nraw=struct.pack("<IH",123,7)\nprint(len(raw),struct.unpack("<IH",raw))\n','6 (123, 7)'),
 ('binary_base64','Base64 编解码','数据','import base64\nraw="中文".encode("utf-8")\nencoded=base64.b64encode(raw)\nprint(base64.b64decode(encoded).decode("utf-8"))\n','中文'),
 ('test_assert','断言与回归','迭代','def add(a,b): return a+b\nfor a,b,expected in [(1,2,3),(-1,1,0),(0,0,0)]:\n    assert add(a,b)==expected\nprint("3 regression cases passed")\n','3 regression cases passed'),
 ('test_unittest','软件单元测试','迭代','import unittest\nclass Tests(unittest.TestCase):\n    def test_sum(self): self.assertEqual(sum([1,2,3]),6)\nresult=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))\nassert result.wasSuccessful()\n','1项unittest成功'),
]

def form_example(index):
    definitions = [('counter','按钮计数','Button',{'text':'计数'}), ('input','文本输入','Entry',{'text':'Hello'}),
        ('check','勾选设置','CheckBox',{'text':'启用'}), ('combo','下拉选择','ComboBox',{'items':['A','B','C']}),
        ('slider','滑块数值','Slider',{}), ('progress','后台进度','ProgressBar',{'value':0}),
        ('list','列表显示','ListBox',{'items':['第一项','第二项']}), ('tabs','标签布局','Tabs',{'tabs':['设置','结果']})]
    identity,title,control,properties = definitions[index]
    model=copy.deepcopy(DEFAULT_FORM)
    model['form']['title']=title
    model['controls']=[ControlModel('Label1','Label','Label1',x=30,y=25,width=400,properties={'text':'窗口就绪'}).to_dict(),
        ControlModel('Demo',control,'Demo',x=30,y=75,width=300,height=60,properties=properties,events={}).to_dict(),
        ControlModel('Button1','Button','Button1',x=30,y=170,properties={'text':'执行'},events={'click':'on_Button1_click'}).to_dict()]
    source='from pcide.runtime_api import ui, tasks\ncount = 0\n\ndef on_main_form_load(event=None):\n    ui.set("Label1", text="'+title+'已加载")\n\ndef on_Button1_click(event=None):\n'
    source+='    global count\n    count += 1\n    ui.set("Label1", text=f"执行次数：{count}")\n'
    if identity=='progress':
        source+='    with tasks.pool(workers=1,capacity=2) as pool:\n        job=pool.submit(lambda cancel: ui.set("Demo",value=100))\n        job.result(2)\n'
    return identity,title,model,source

NATIVE = [
 ('native_c','C 小型工具','c-console','#include <stdio.h>\nint main(void){printf("C_NATIVE_OK\\n");return 0;}\n'),
 ('native_sort','C++ 排序','cpp-console','#include <algorithm>\n#include <iostream>\n#include <vector>\nint main(){std::vector<int> v{3,1,2};std::sort(v.begin(),v.end());for(auto n:v)std::cout<<n;std::cout<<"\\n";}\n'),
 ('native_thread','C++ 线程回收','cpp-console','#include <thread>\n#include <iostream>\nint main(){int result=0;std::thread t([&]{result=42;});t.join();std::cout<<result<<"\\n";}\n'),
 ('native_future','C++ 异步结果','cpp-console','#include <future>\n#include <iostream>\nint main(){auto f=std::async(std::launch::async,[]{return 42;});std::cout<<f.get()<<"\\n";}\n'),
 ('native_raii','C++ 智能指针','cpp-console','#include <memory>\n#include <iostream>\nint main(){auto p=std::make_unique<int>(42);std::cout<<*p<<"\\n";}\n'),
 ('native_factory','C++ 工厂','cpp-console','#include <memory>\n#include <iostream>\nstruct Product{virtual ~Product()=default;virtual int value()const=0;};\nstruct Tool:Product{int value()const override{return 42;}};\nstd::unique_ptr<Product> create(){return std::make_unique<Tool>();}\nint main(){std::cout<<create()->value()<<"\\n";}\n'),
 ('native_win32','Win32 原生提示框','cpp-win32',None),
 ('native_file','C++ 文件 RAII','cpp-console','#include <fstream>\n#include <iostream>\nint main(){{std::ofstream out("data.txt");out<<"hello";}std::ifstream in("data.txt");std::string text;in>>text;std::cout<<text<<"\\n";}\n'),
 ('native_mutex','C++ 互斥共享数据','cpp-console','#include <thread>\n#include <mutex>\n#include <iostream>\nint main(){int n=0;std::mutex m;auto work=[&]{for(int i=0;i<100;++i){std::lock_guard<std::mutex> lock(m);++n;}};std::thread a(work),b(work);a.join();b.join();std::cout<<n<<"\\n";}\n'),
 ('native_cmake','CMake 增量工程','cpp-cmake',None),
]
CSHARP = [
 ('cs_console','C# 系统运行时','csharp-console','using System;\nConsole.WriteLine("CS_SYSTEM_OK");\n'),
 ('cs_factory','C# 工厂复用','csharp-console','using System;\nvar factory = new Func<int>(() => 42);\nConsole.WriteLine(factory());\n'),
 ('cs_async','C# 异步任务','csharp-console','using System;\nusing System.Threading.Tasks;\nConsole.WriteLine(await Task.Run(() => 42));\n'),
 ('cs_cancel','C# 协作取消','csharp-console','using System;\nusing System.Threading;\nusing System.Threading.Tasks;\nusing var token=new CancellationTokenSource();\ntoken.Cancel();\ntry { await Task.Delay(1000,token.Token); } catch(OperationCanceledException) { Console.WriteLine("cancelled"); }\n'),
 ('cs_json','C# JSON 数据','csharp-console','using System;\nusing System.Text.Json;\nConsole.WriteLine(JsonSerializer.Serialize(new[]{1,2,3}));\n'),
 ('cs_window','C# Windows Forms 窗口','csharp-winforms',None),
]

def web_source(index):
    bodies = [
        '<button id="b">计数</button><p id="o">0</p><script>let n=0;b.onclick=()=>o.textContent=++n;</script>',
        '<input id="a" type="number" value="1"><input id="b" type="number" value="2"><button id="go">相加</button><p id="o"></p><script>go.onclick=()=>o.textContent=Number(a.value)+Number(b.value);</script>',
        '<input id="task"><button id="add">添加任务</button><ul id="list"></ul><script>add.onclick=()=>{let li=document.createElement("li");li.textContent=task.value;li.onclick=()=>li.remove();list.append(li);task.value="";};</script>',
        '<textarea id="text">示例笔记</textarea><button id="save">保存到浏览器</button><script>text.value=localStorage.getItem("pcide-note")||text.value;save.onclick=()=>localStorage.setItem("pcide-note",text.value);</script>',
        '<canvas id="c" width="600" height="300"></canvas><script>const ctx=c.getContext("2d");let frame,x=30;function tick(){ctx.clearRect(0,0,600,300);x=(x+2)%600;ctx.fillStyle="#1689ce";ctx.fillRect(x,130,30,30);frame=requestAnimationFrame(tick);}tick();addEventListener("pagehide",()=>cancelAnimationFrame(frame),{once:true});</script>',
        '<canvas id="c" width="600" height="300"></canvas><p>鼠标点击移动圆球</p><script>const ctx=c.getContext("2d");function draw(x,y){ctx.clearRect(0,0,600,300);ctx.beginPath();ctx.arc(x,y,20,0,Math.PI*2);ctx.fill();}c.onclick=e=>{const r=c.getBoundingClientRect();draw((e.clientX-r.left)*c.width/r.width,(e.clientY-r.top)*c.height/r.height);};draw(100,100);</script>',
    ]
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>PCIDE Example</title><style>body{font:18px system-ui;margin:2rem}button,input{padding:.6rem}canvas{border:1px solid #aaa}</style>'+bodies[index]+'</html>\n'

def main():
    paths=Paths(root)
    paths.projects=root/'examples/projects'
    catalog=[]
    def add(identity,title,category,template,source=None,expected='',form=None):
        target=paths.project(identity)
        if target.exists():
            raise RuntimeError('示例已存在，拒绝覆盖：'+str(target))
        project=create_project(paths,identity,template)
        if source is not None: project.entry_path.write_text(source,encoding='utf-8')
        if form is not None: project.save_form(form)
        requires = 'IDE 已有脚本运行时；无需下载' if project.manifest['language'] in {'python','zhxb','javascript','typescript'} else {
            'c':'已安装 C 编译器；不下载', 'cpp':'已安装 C++ 编译器（CMake示例还需CMake）；不下载',
            'csharp':'Unity Editor 与 Windows Build Support' if template.startswith('unity') else '已安装 .NET 8+ SDK / 对应运行时；不下载',
            'html':'系统浏览器', 'gdscript':'Godot 4 与 Windows 导出模板；不下载'}[project.manifest['language']]
        if template.startswith('unity'): expected=expected or '打开Unity后使用PCIDE/Create Demo Scene，再按Play；IDE构建生成game.exe'
        if template.startswith('godot'): expected=expected or 'F5运行实际场景；构建导出game.exe'
        expected=expected or ('编译生成真实app.exe，F5运行；源码展示该示例的行为')
        description=f'{title}：完整工程、入口源码与使用说明；可修改后再次运行/编译进行迭代。'
        readme=f'# {title}\n\n{description}\n\n## 需要\n\n{requires}\n\n## 操作\n\n1. 帮助 → 示例中心，双击本例创建可编辑副本。\n2. 阅读入口源码；窗口例在界面设计页查看控件与事件。\n3. F5运行；编译菜单选择目标；停止可取消后台任务。\n4. 修改源码或表单后再次运行/构建。原示例不会被覆盖。\n\n## 预期结果\n\n{expected}\n\n## 编译与资源\n\n脚本独立EXE会携带运行时；系统环境发布不附带运行时。C/C++静态CRT仍依赖Windows系统DLL。\n线程例使用有界池和协作取消，with/RAII/using释放资源。引擎示例需实际本机引擎，未安装时不会假装执行成功。\n'
        (project.root/'README.md').write_text(readme,encoding='utf-8')
        catalog.append({'id':identity,'title':title,'category':category,'template':template,'path':'projects/'+identity,
            'description':description,'expected':expected,'requires':requires})
    if len(PYTHON)!=60: raise RuntimeError(f'Python例数量应为60，实际{len(PYTHON)}')
    for identity,title,category,source,expected in PYTHON:
        add(identity,title,category,'python-script',source,expected)
    for index in range(8):
        identity,title,model,source=form_example(index)
        add('ui_'+identity,title,'窗口交互','python-form',source,'窗口加载后显示标题；点击执行更新计数，后台进度例还更新进度条。',model)
    for template,identity,title in [('zhxb-script','zh_console','中文源码输出'),('javascript-script','js_json','JavaScript 数据处理'),
                                  ('typescript-script','ts_typed','TypeScript 类型示例'),('javascript-form','js_window','JavaScript 窗口事件')]:
        source={'js_json':'const items=[1,2,3];\nconsole.log(JSON.stringify(items.map(n=>n*2)));\n',
                'ts_typed':'interface Item {name:string;value:number}\nconst item:Item={name:"PCIDE",value:42};\nconsole.log(item);\n'}.get(identity)
        add(identity,title,'多语言',template,source, '输出结果或点击窗口按钮触发事件')
    for identity,title,template,source in NATIVE: add(identity,title,'原生软件',template,source)
    for identity,title,template,source in CSHARP: add(identity,title,'C# 软件',template,source)
    for index,title in enumerate(['网页计数器','网页计算器','任务列表','本地笔记','Canvas 动画','Canvas 鼠标交互']):
        add('web_'+str(index+1),title,'网页与小游戏','web-app',web_source(index),'F5打开浏览器，操作按钮或Canvas查看实际交互')
    for template,identity,title in [('unity-2d','unity_rotate','Unity 2D 旋转'),('unity-3d','unity_cube','Unity 3D 方块'),('unity-3d','unity_move','Unity 3D 移动')]:
        source=None if identity!='unity_move' else 'using UnityEngine;\npublic sealed class GameController:MonoBehaviour { void Update(){ transform.position=new Vector3(Mathf.Sin(Time.time)*2,0,0); } }\n'
        add(identity,title,'Unity 游戏',template,source)
    for template,identity,title in [('godot-2d','godot_ball','Godot 移动圆球'),('godot-3d','godot_cube','Godot 3D 方块'),('godot-2d','godot_input','Godot 键盘移动')]:
        source=None if identity!='godot_input' else 'extends Node2D\nvar point:=Vector2(200,200)\nfunc _process(delta):\n    point+=Input.get_vector("ui_left","ui_right","ui_up","ui_down")*200*delta\n    queue_redraw()\nfunc _draw():\n    draw_circle(point,20,Color.CORNFLOWER_BLUE)\n'
        add(identity,title,'Godot 游戏',template,source)
    if len(catalog)!=100: raise RuntimeError('示例数量不等于100')
    atomic_write_json(root/'examples/catalog.json',{'version':1,'examples':catalog})
    (root/'examples/README.md').write_text('# 完整示例目录\n\n共100个不同工程。在IDE的欢迎页或帮助 → 示例中心按类别/关键词筛选，双击创建副本。\n\n'+
        '\n'.join(f'- [{i["title"]}]({i["path"]}/README.md)：{i["category"]}' for i in catalog)+'\n',encoding='utf-8')
    print('Created',len(catalog),'examples')

if __name__=='__main__': main()
