import os
from time import sleep
import os

from tools import execute_code_in_repl
from vertexai.generative_models import (
    Content,
    FunctionDeclaration,
    Part,
    Tool,
)
from tools import execute_code_in_repl
import agent_utils
from typing import Literal

import vertexai
import operator
from typing import Annotated, Sequence, TypedDict
import traceback




from langgraph.graph import END, StateGraph, START

# Optional, add tracing in LangSmith
os.environ["LANGSMITH_API_KEY"]="<Key Here>"
os.environ["LANGCHAIN_TRACING_V2"] = "<Key Here>"
os.environ["LANGCHAIN_PROJECT"] = "<Key Here"

PROJECT_ID = "<Project id>"  
LOCATION = "<location here>"  



vertexai.init(project=PROJECT_ID, location=LOCATION)

from typing import Annotated

exec_python_code_dcl = FunctionDeclaration(
    name="exec_python_code",
    description="Run the python code in REPL",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Code to execute"}},
    },
)

code_tool = Tool(
    function_declarations=[
        exec_python_code_dcl,
    ],
)

def create_agent(model_name, system_instruction: str, tools: list = []):
    """Create an agent."""
    agent_inst = agent_utils.Agent(model_name, system_instruction, tools)
    return agent_inst.generate_content


# This defines the object that is passed between each node
# in the graph. We will create different nodes for each agent and tool
class AgentState(TypedDict):
    contents: Annotated[Sequence[Content], operator.add]
    sender: str

state = AgentState()

import functools

from langchain_core.messages import AIMessage

tool_functions = {
    'exec_python_code': execute_code_in_repl
}

# Helper function to create a node for a given agent
def agent_node(state, agent, name):
    result = agent(state)
    return {
        "contents": [result],
        "sender": name,
    }


# Supervisor
supervisor_agent = create_agent(
    model_name="gemini-1.5-pro-001",
    system_instruction="You are a supervisor tasked with managing a conversation between the"
    " following workers:  [code_generator, code_reviewer, code_executor]. Given the following user request,"
    " respond with only the worker that needs to act next. Each worker will perform a"
    " task and respond with their results and status. The produced artifacts need to be of high quality. When finished executing the code,"
    " respond with FINISH. You will NOT perform the the requested taks, but will always use the workers."
)
supervisor_node = functools.partial(agent_node, agent=supervisor_agent, name="Supervisor")

# coder
coder_agent = create_agent(
    model_name="gemini-1.5-pro-001",
    system_instruction="You are a coder. You write python code for the given problem statement. If the code reviewer provides any review comments to improve the code you will rewrite the code to incorporate the review comments.",
)
coder_node = functools.partial(agent_node, agent=coder_agent, name="code_generator")

#Code reviewer
code_reviewer_agent = create_agent(
    model_name="gemini-1.5-pro-001",
    system_instruction="You are a code reviewer. You will ensure that the generated code to ensure the code is of high quality. ",
)
code_reviewer_node = functools.partial(agent_node, agent=code_reviewer_agent, name="code_reviewer")



# coder executor
code_exec_agent = create_agent(
    model_name="gemini-1.5-pro-001",
    tools=[code_tool],
    system_instruction="You are a code executor. You will execute the python code that have been reviewed and approved by the code reviewer. you have access to the tool exec_python_code_dcl. Use this tool to execute the python code.",
)
code_exec_node = functools.partial(agent_node, agent=code_exec_agent, name="code_executor")

# This is the router
def router(state) -> Literal["code_generator","code_reviewer","code_executor", "Supervisor", "__end__"]:
    #Sleep to avoid hitting QPM limits
    sleep(10)
    contents = state["contents"]
    
    last_message_text = contents[-1].parts[0].text


    if "code_reviewer" in last_message_text:
 
        return "code_reviewer"
    if "code_generator" in last_message_text:

        return "code_generator"
    if "code_executor" in last_message_text:

        return "code_executor"
    if "FINISH" in last_message_text:
        # Any agent decided the work is done
        return "__end__"
    
    return "Supervisor"
workflow = StateGraph(AgentState)

workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("code_generator", coder_node)
workflow.add_node("code_reviewer", code_reviewer_node)
workflow.add_node("code_executor", code_exec_node)


workflow.add_conditional_edges(
    "Supervisor",
    router,
    {"code_generator": "code_generator","code_reviewer": "code_reviewer","code_executor": "code_executor", "__end__": END},
)

workflow.add_edge(
    "code_generator",
    "Supervisor",
)

workflow.add_edge(
    "code_reviewer",
    "Supervisor",
)
workflow.add_edge(
    "code_executor",
    "Supervisor",
)

workflow.add_edge(START, "Supervisor")
graph = workflow.compile()

try:
    grph = graph.get_graph(xray=True)
    grph.print_ascii()


except Exception as e:
    # This requires some extra dependencies and is optional
    print(traceback.format_exc())
    pass
state["contents"] = [Content(role="user", parts=[Part.from_text("Find the first 100 elements of fibonacci series. Then pick 2 random numbers from this list and compute their average.")])]
state["sender"]="Supervisor"
events = graph.stream(
    {
        "contents" : state["contents"],
    },
    # Maximum number of steps to take in the graph
    {"recursion_limit": 150},
)
for s in events:
    print(s)
    print("----")

