# Python asyncio 异步并发教学笔记

> 面向本项目的实战学习笔记。配套真实代码：`backend/app/api/routers/analysis.py` 与 `chat.py` 的 SSE 端点。

---

## 0. 一句话心法

asyncio 的本质是：**用一个线程，把"等待的时间"填满**。

- 凡是"要等"的地方（网络、IO、LLM 调用），用 `await` 让出控制权；
- 凡是"要算"的地方（CPU 密集），asyncio 帮不了你，得用线程/进程。

---

## 1. 基础语法：get_running_loop 与 asyncio.Queue

```python
loop = asyncio.get_running_loop()          # 拿到当前正在运行的事件循环
queue: asyncio.Queue = asyncio.Queue()     # 建一个协程间安全传数据的异步队列
```

- `get_running_loop()` 只能在 `async def` 内部（或循环回调里）调用，否则抛 `RuntimeError: no running event loop`。
- `queue: asyncio.Queue` 中的冒号是**类型注解**（PEP 526），只给 IDE / mypy 看，运行时**完全忽略**。
- `asyncio.Queue` 是**单线程内**的异步队列：`await q.put(x)` / `await q.get()` 在空/满时会挂起自己、让出控制权，不阻塞线程。

---

## 2. run / gather / create_task 三兄弟

| | `asyncio.run(coro)` | `await asyncio.gather(*coros)` | `asyncio.create_task(coro)` |
|---|---|---|---|
| 角色 | 程序**入口**（总开关） | **批量并发 + 等待** | **后台启动，不等待** |
| 调用位置 | 只能在普通同步代码 | 只能在 `async def` 内，需 `await` | 只能在 `async def` 内 |
| 是否等待 | 阻塞到全部结束 | 等**全部**完成 | **不等**，立刻返回 |
| 返回 | 协程的返回值 | 结果**列表**（按传入顺序） | 一个 `Task` 句柄 |

```python
asyncio.run(main())                     # 只收一个协程，是异步世界的唯一入口
results = await asyncio.gather(a(), b(), c())   # 并发跑，按传入顺序收结果
task = asyncio.create_task(fetch(url))  # 先启动，主流程继续干别的，之后 await task 收结果
```

要点：

- `run` 只收**一个协程对象**；要多任务就把它们包进一个 `main` 协程，再交给 `run`。
- `gather` 内部其实是把每个协程都 `create_task` 包成 Task，再一起 `await`——它是 `create_task` 的"批量便捷封装"。
- 参数要在调用协程函数时就传好：`asyncio.run(main("hello", 3))`。

---

## 3. 核心概念：并发 vs 并行（命门）

- **并发 concurrent**：单线程内**交替**执行，同一时刻只有一个在跑（asyncio 属于这类）。
- **并行 parallel**：多线程/多核**同时**执行。

asyncio 全程**只有一个线程**，价值在于把"等待 IO 的时间"利用起来去干别的。

> 类比：一个厨师（单线程）同时照看两道菜——菜 A 下锅等煮时，转身去切菜 B，再回来翻 A。看起来同时，其实手一次只做一件事，但等待时间被填满了。

---

## 4. Coroutine / Task / Future 三件套

```
协程对象 (Coroutine)  —— 一段"还没开始执行"的代码描述（调用 async def 函数得到，函数体还没跑）
        │  create_task() / 被 await / 传给 run
        ▼
Task                 —— 被事件循环"接管"的运行单元，有状态（运行中/完成/取消）
        │  (Task 是 Future 的子类)
        ▼
Future               —— "未来才会有的结果"的占位盒
```

主线：**协程不自己跑，必须被包装成 Task 或被 await 才会被事件循环驱动。**

Task 常用操作：`await task`（等结果）、`task.cancel()`、`task.done()`、`task.result()`。

---

## 5. await 到底发生了什么

```python
result = await fetch()
```

1. `fetch()` 被提交给事件循环；
2. 当前协程**挂起**，把控制权交还给事件循环；
3. 事件循环转去运行其它在等的协程；
4. `fetch()` 完成后，事件循环唤醒当前协程继续往下走。

所以 `await` 不是"阻塞等待"，而是"我先让开，等好了叫我"。

⚠️ 因此 async 里绝不能用 `time.sleep`（睡死整条线程、卡死所有协程），要用 `await asyncio.sleep`（只睡自己）。

---

## 6. 更细粒度的等待控制

| 工具 | 等什么 | 返回顺序 |
|------|-------|---------|
| `gather` | 等**全部** | 传入顺序 |
| `wait` | 可等任一/全部/异常 | 给 done/pending 集合 |
| `as_completed` | 逐个出 | **完成**顺序 |
| `wait_for` | 单个 + 超时 | 单个 |

```python
await asyncio.wait_for(slow(), timeout=3.0)                 # 超时抛 TimeoutError
done, pending = await asyncio.wait(tasks, return_when=FIRST_COMPLETED)
for coro in asyncio.as_completed(tasks):                    # 谁先完成谁先出
    r = await coro
```

---

## 7. 并发控制：Semaphore / Lock

```python
sem = asyncio.Semaphore(5)      # 最多同时 5 个
async def fetch(url):
    async with sem:             # 拿到许可证才进，满了排队等
        ...
```

- `Semaphore(n)`：限流并发数（如爬 N 个网页时打爆服务器）。
- `Lock()`：异步锁，同一时刻只允许一个协程进临界区（`await lock.acquire()` 不阻塞线程）。

---

## 8. 常见坑

1. **async 里调用阻塞函数**（`time.sleep`、`requests.get`、大文件 `read`）→ 卡死整个循环。改用 async 版本，或丢线程池：
   ```python
   result = await asyncio.to_thread(requests.get, url)
   ```
2. **create_task 后忘 await** → Task 被垃圾回收，任务半途而废。要么保存引用，要么放进集合 + `add_done_callback` 清理。
3. **`async def` 里忘 `await`**：`fetch()` 只是创建协程对象，什么都没执行，还报 "never awaited" 警告。

---

## 9. 技术选型决策

| 场景 | 用什么 |
|------|-------|
| 大量 IO 等待（网络/数据库/API/LLM 调用） | ✅ **asyncio** |
| CPU 密集计算 | **多进程** `multiprocessing` |
| 有现成阻塞库、不想大改 | **线程池** `ThreadPoolExecutor` |
| 既有 IO 并发又有 CPU 并行 | asyncio + `run_in_executor` 混合 |

为什么协程比线程轻：线程切换要内核态保存/恢复上下文，几万线程内存就爆；协程切换只在用户态、由事件循环调度，单进程能开几十万个协程。

---

## 10. 项目实战对照

本项目的 SSE 端点用的是 **"asyncio.Queue + 后台线程"** 混合模型（因为 `graph.stream` 里是阻塞的 LLM 调用，不能写成协程）。详见：
- `backend/app/api/routers/analysis.py` 的 `POST /api/analysis`（L30-59）
- `backend/app/api/routers/chat.py` 的 `POST /api/chat/stream`（L82-130）
- 服务入口 `backend/run_server.py`（uvicorn 充当 `asyncio.run` 的角色）

核心桥接句：`loop.call_soon_threadsafe(queue.put_nowait, ev)` —— 因为 `asyncio.Queue` **非线程安全**，worker 线程不能直接 `put`，必须经 `call_soon_threadsafe` 投递回事件循环线程执行。
