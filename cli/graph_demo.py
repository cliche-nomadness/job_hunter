# Langgraph最小示例

from typing import TypedDict
from langgraph.graph import StateGraph, START, END
class State(TypedDict):   #定义state:节点之间传递的数据
    messages: list[str]

def node_a(state: State) -> State:   #节点 = 普通函数
    return {"messages": state["messages"] + ["A 处理了"]}

def node_b(state: State) -> State:
    return {"messages": state["messages"] + ["B 处理了"]}

builder = StateGraph(State) # 建图
builder.add_node("a", node_a) #注册节点
builder.add_node("b", node_b)
builder.add_edge(START, "a") #添加边
builder.add_edge("a", "b") # a → b
builder.add_edge("b", END) # b → 出口
graph = builder.compile() # 编译为可执行图

result = graph.invoke({"messages": []}) # 从入口跑， 沿着边走
print(result)                            #{'messages':['A 处理了','B 处理了']}