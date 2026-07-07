# -*- coding: utf-8 -*-
"""
RAG 语义检索物理阈值大规模基准测试 - 纯净工程技术教学语料库校准版 (Clean Engineering Corpus)
执行指令: python backend/scripts/benchmark_rag_threshold.py
"""
import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.services.chroma_client import chroma_rag_client

def prepare_clean_engineering_knowledge_base():
    """彻底清空历史残留切片（如修仙小说等非核心教学语料），只注入纯净的 STM32 / FreeRTOS / 硬件工程真讲义"""
    collection = chroma_rag_client._get_collection("classroom_knowledge")
    existing_data = collection.get()
    if existing_data and existing_data.get('ids'):
        print(f"🧹 正在清空旧切片残留共 {len(existing_data['ids'])} 条，确保物理特征绝对纯净...")
        collection.delete(ids=existing_data['ids'])

    files_content = {
        "01_硬件_GPIO_GPIO初始化结构体与模式解析.md": """
# STM32 GPIO 初始化结构体与八种工作模式深度解析
GPIO（General Purpose Input Output）通用输入输出端口是 STM32 最基础的外设。
在 STM32 标准库中，通过 `GPIO_InitTypeDef` 结构体配置引脚：
1. `GPIO_Pin`：指定引脚号，如 `GPIO_Pin_0 | GPIO_Pin_13`。
2. `GPIO_Mode`：引脚工作模式，包含四种输入模式与四种输出模式：
   - 浮空输入（`GPIO_Mode_IN_FLOATING`）：引脚电平不确定，完全由外部信号决定，常用于按键或通信接收。
   - 上拉输入（`GPIO_Mode_IPU`）与下拉输入（`GPIO_Mode_IPD`）：内部通过上拉或下拉电阻锁定默认电平。
   - 模拟输入（`GPIO_Mode_AIN`）：关闭数字缓冲区，供 ADC 模数转换使用。
   - 推挽输出（`GPIO_Mode_Out_PP`）：P-MOS 与 N-MOS 轮流导通，具备强高低电平驱动能力，最大输出电流可达 25mA。
   - 开漏输出（`GPIO_Mode_Out_OD`）：仅 N-MOS 工作，输出高电平时处于高阻态，必须外接上拉电阻，支持“线与”特性，常用于 I2C 总线。
   - 复用推挽输出（`GPIO_Mode_AF_PP`）与复用开漏输出（`GPIO_Mode_AF_OD`）：由外设（如 SPI、USART、I2C）直接控制引脚。
3. `GPIO_Speed`：响应速率配置，例如 `GPIO_Speed_50MHz`。
在调用 `GPIO_Init(GPIOA, &GPIO_InitStructure)` 前，务必执行 `RCC_APB2PeriphClockCmd(RCC_APB2Periph_GPIOA, ENABLE)` 开启总线时钟。
""",
        "02_硬件_STM32时钟树与NVIC嵌套向量中断控制器.md": """
# STM32 系统时钟树 (Clock Tree) 与 NVIC 中断优先级控制器
STM32 采用复杂的时钟树设计以降低功耗：
1. HSE（外部高速时钟）：通常接 8MHz 石英晶振，通过 PLL 锁相环倍频至最高 72MHz，作为系统核心时钟 (SYSCLK)。
2. AHB 总线（高级高性能总线）：直接连接 Cortex-M3 内核、Flash 与 DMA 控制器，时钟频率通常为 72MHz。
3. APB1/APB2 总线：外设挂载总线。APB2 负责高速外设（如 GPIO、USART1、SPI1、ADC1），最大上限为 72MHz；APB1 负责低速外设（如 TIM2~7、USART2~5、I2C、CAN），最高限速 36MHz。
关于 NVIC（嵌套向量中断控制器）：
STM32 从 Cortex-M 架构中支持 16 个可编程中断优先级。通过 `NVIC_PriorityGroupConfig(NVIC_PriorityGroup_2)` 将优先级拆分为 2 位抢占优先级 (Preemption Priority，范围 0~3) 和 2 位响应优先级 (Sub Priority，范围 0~3)。
抢占优先级高者可直接打断正在执行的低抢占优先级中断函数，实现嵌套响应；抢占优先级相同则看响应优先级，响应优先级不具有嵌套打断能力。
""",
        "03_硬件_USART串口通信与波特率计算.md": """
# STM32 USART 串口异步通信与波特率计算
USART（通用同步异步收发器）是嵌入式开发中最常用的调试与全双工通信接口。
1. 引脚排布：TX（发送端，须配置为复用推挽输出 `GPIO_Mode_AF_PP`），RX（接收端，须配置为浮空输入 `GPIO_Mode_IN_FLOATING`）。
2. `USART_InitTypeDef` 核心参数：
   - `USART_BaudRate`：通信波特率，典型值为 `9600`、`115200`。
   - `USART_WordLength`：数据帧长度，通常选 `USART_WordLength_8b`。
   - `USART_StopBits`：停止位，选 `USART_StopBits_1`。
   - `USART_Parity`：奇偶校验位，通常选择无校验 `USART_Parity_No`。
3. 中断接收编程：开启串口接收中断需调用 `USART_ITConfig(USART1, USART_IT_RXNE, ENABLE)`。当寄存器 RXNE（接收数据寄存器非空）置位时，触发中断请求并进入 `USART1_IRQHandler` 服务函数。
""",
        "04_硬件_DMA直接内存访问控制器编程原理.md": """
# STM32 DMA 直接内存访问控制器原理与多通道配置
DMA（Direct Memory Access）直接内存访问控制器，旨在在不需要 CPU 干预的情况下，实现外设寄存器与内存（SRAM）、或内存与内存之间的高速数据传输。
1. 通道分配：STM32F103 具有 DMA1（7个通道）和 DMA2（5个通道）。每个通道有固定的外设请求源映射，例如 ADC1 挂载于 DMA1_Channel1，USART1_TX 挂载于 DMA1_Channel4。
2. 核心传输配置 `DMA_InitTypeDef`：
   - `DMA_PeripheralBaseAddr`：外设目标基地址（如 `&ADC1->DR` 或 `&USART1->DR`）。
   - `DMA_MemoryBaseAddr`：内存缓冲区基地址（如单片机 C 语言中的全局数组 `rx_buffer`）。
   - `DMA_DIR`：数据传输方向，`DMA_DIR_PeripheralSRC` 为外设到内存，`DMA_DIR_PeripheralDST` 为内存到外设。
   - `DMA_BufferSize`：一次整体传输的数据单元数量。
   - `DMA_PeripheralInc` 与 `DMA_MemoryInc`：地址自增模式，外设寄存器通常设为 Disable（固定不变），数组缓冲区通常设为 Enable（自动后移）。
   - `DMA_Mode`：工作模式，可选单次传输 `DMA_Mode_Normal` 或循环缓存模式 `DMA_Mode_Circular`。
""",
        "05_软件_FreeRTOS实时操作系统任务调度与互斥锁.md": """
# FreeRTOS 实时操作系统：任务调度、信号量与互斥锁
在单片机中引入 FreeRTOS 可实现多任务并发处理。
1. 任务调度原理：FreeRTOS 采用基于优先级的抢占式时间片轮转调度算法。调度器通过 SysTick 滴答定时器产生周期性中断（通常为 1ms，即 configTICK_RATE_HZ = 1000）。当更高优先级的任务就绪时，调度器会立即执行上下文切换（Context Switch）。
2. 任务创建接口：`xTaskCreate(TaskFunction, "TaskName", StackSize, Parameter, Priority, &TaskHandle)`。
3. 任务同步与互斥：
   - 二值信号量（Binary Semaphore）：用于任务与中断同步，但容易引发优先级翻转（Priority Inversion）问题。
   - 互斥信号量（Mutex）：拥有优先级继承（Priority Inheritance）机制！当高优先级任务企图获取一个已被低优先级任务锁定的互斥锁时，系统会自动临时提升低优先级任务的优先级，防止中等优先级任务打断从而解决优先级翻转问题。调用 API：`xSemaphoreCreateMutex()`、`xSemaphoreTake()` 和 `xSemaphoreGive()`。
"""
    }
    print("📥 正在向纯净 ChromaDB 索引注入 5 份标准技术工程真讲义...")
    res = chroma_rag_client.sync_knowledge(files_content)
    print(f"✅ {res.get('message', res)}")

def run_benchmark():
    print("\n" + "=" * 70)
    print("🔬 启动纯净工程语料库 RAG 物理距离分布与分离区间基准测试")
    print("=" * 70)
    
    prepare_clean_engineering_knowledge_base()
    
    collection = chroma_rag_client._get_collection("classroom_knowledge")
    count = collection.count()
    print(f"📦 当前纯净技术知识库切片总数: {count} 块\n")

    # 测试套件 A：纯口语、问候与无意义闲聊 (Suite A: Pure Casual Chat)
    suite_a = [
        "你好", "早上好", "吃了没", "嗨", "今天天气真好", 
        "哈哈哈", "太棒了", "谢谢你", "好的", "嗯嗯", 
        "原来如此", "拜拜", "晚安", "卧槽", "流弊", 
        "对对对", "不用了", "在吗", "你是谁", "干嘛呢",
        "辛苦了", "笑死我了", "没错", "真是太厉害了", "好吧"
    ]

    # 测试套件 B：口语状态沟通、吐槽、无具体专业名词的追问 (Suite B: Conversational / Meta-status)
    suite_b = [
        "呃呃呃", "现在呢？", "依旧没解决", "还是不行", "然后呢", 
        "下一步干嘛", "为什么啊", "你懂了没", "能不能说简单点", "重试一下", 
        "快点", "我看不到", "报错了", "帮我看看", "什么鬼", 
        "哪里出错了", "怎么搞", "接着讲", "讲讲第二章", "第3节说啥了",
        "刚刚那个不对", "搞定了没", "重新生成一次", "我看不懂这段", "老样子"
    ]

    # 测试套件 C：真正嵌入式技术、外设、C代码与操作系统深度提问 (Suite C: Genuine Domain Knowledge)
    suite_c = [
        "怎么配置GPIO引脚？", "STM32中断优先级是什么？", "什么是推挽输出模式？", 
        "开漏输出为什么需要上拉电阻？", "通用输入输出端口有几种工作模式？", 
        "如何设置NVIC中断向量表？", "STM32时钟树怎么配置？", "讲述一下AHB和APB总线的区别", 
        "GPIO浮空输入和上拉输入有什么区别？", "USART串口接收数据非空寄存器RXNE怎么用？", 
        "USART异步串口波特率该怎么设置？", "DMA直接内存访问控制器有什么用？", 
        "怎么配置DMA的外设基地址和内存增量模式？", "FreeRTOS任务如何创建和调度？", 
        "什么是优先级翻转？互斥锁Mutex是如何解决优先级翻转的？",
        "APB1和APB2的时钟最大限制分别是多少兆赫兹？", "什么叫抢占优先级与响应优先级？", 
        "DMA的循环缓存模式在什么时候使用？"
    ]

    def test_suite(name, queries):
        print(f"\n" + "─" * 70)
        print(f"📊 测试套件 [{name}] (共 {len(queries)} 个样本)")
        print("─" * 70)
        
        results = collection.query(query_texts=queries, n_results=1, include=['documents', 'distances'])
        distances = [d[0] for d in results['distances']]
        docs = [doc[0][:28].replace("\n", " ") for doc in results['documents']]
        
        for q, dist, doc in zip(queries, distances, docs):
            print(f"[{dist:.4f}] | 问: {q:<18} | 匹配讲义: {doc}...")
            
        min_d = min(distances)
        max_d = max(distances)
        mean_d = sum(distances) / len(distances)
        print(f"\n📈 统计摘要 [{name}] -> 最小值: {min_d:.4f} | 最大值: {max_d:.4f} | 平均距离: {mean_d:.4f}")
        return distances

    dist_a = test_suite("Suite A: 纯闲聊/日常招呼", suite_a)
    dist_b = test_suite("Suite B: 口语状态追问/吐槽/模糊沟通", suite_b)
    dist_c = test_suite("Suite C: 硬件技术讲义/FreeRTOS深度提问", suite_c)

    print("\n" + "=" * 70)
    print("🎯 物理距离分布深度对比分析 (Physical Distance Analysis)")
    print("=" * 70)
    print(f"Suite A (纯闲聊)         : 物理距离范围 [{min(dist_a):.4f}  ~  {max(dist_a):.4f}], 均值 = {sum(dist_a)/len(dist_a):.4f}")
    print(f"Suite B (口语/状态追问)  : 物理距离范围 [{min(dist_b):.4f}  ~  {max(dist_b):.4f}], 均值 = {sum(dist_b)/len(dist_b):.4f}")
    print(f"Suite C (真实硬核技术提问): 物理距离范围 [{min(dist_c):.4f}  ~  {max(dist_c):.4f}], 均值 = {sum(dist_c)/len(dist_c):.4f}")
    
    print("\n【物理门控阈值收敛扫描矩阵】 (寻找闲聊误报率接近0%且知识召回率最高的分界点):")
    best_thresh = None
    for thresh in [0.65, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80, 0.82, 0.83, 0.85, 0.88, 0.90, 0.95, 1.00, 1.20]:
        pass_a = sum(1 for d in dist_a if d <= thresh)
        pass_b = sum(1 for d in dist_b if d <= thresh)
        pass_c = sum(1 for d in dist_c if d <= thresh)
        
        rate_a = pass_a / len(dist_a) * 100
        rate_b = pass_b / len(dist_b) * 100
        rate_c = pass_c / len(dist_c) * 100
        
        mark = ""
        if pass_a == 0 and pass_b == 0 and rate_c >= 80.0:
            mark = " 🔒 [绝对安全门限 (0 False Positives)]"
            if best_thresh is None:
                best_thresh = thresh
        elif pass_a <= 1 and pass_b <= 1 and rate_c >= 90.0:
            mark = " 🌟 [高召回黄金门限 (Recommended)]"
                
        print(f"阈值 dist <= {thresh:.2f} -> 闲聊误放行(A): {pass_a:2d}/{len(dist_a)} ({rate_a:5.1f}%) | "
              f"状态误放行(B): {pass_b:2d}/{len(dist_b)} ({rate_b:5.1f}%) | "
              f"讲义真召回(C): {pass_c:2d}/{len(dist_c)} ({rate_c:5.1f}%){mark}")

if __name__ == "__main__":
    run_benchmark()
