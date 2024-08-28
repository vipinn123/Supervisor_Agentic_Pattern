from vertexai.generative_models import (
    Content,
    GenerationConfig,
    GenerativeModel,
    Part,
)

from tools import execute_code_in_repl

class Agent:

    def __init__(self, model_name, system_instruction: str, tools: list = []):

        llm = GenerativeModel(
            model_name=model_name,
            generation_config=GenerationConfig(temperature=0),

            system_instruction=system_instruction,
            tools=tools, 
        )
        self.llm=llm


    def send_message(self, messages):
        return self.chat.send_message(messages)
    
    def generate_content(self, state):

        role = state["contents"][-1].role

        response = self.llm.generate_content(contents=state["contents"])


        if response.candidates[0].content.parts[0].function_call:
            function_name = response.candidates[0].content.parts[0].function_call.name
            query  =response.candidates[0].content.parts[0].function_call.args["query"]
            if function_name == "exec_python_code":
                api_response = execute_code_in_repl(query)
                if api_response is not None:

                    return Content(role="user", parts=[Part.from_text(api_response)])
        
    
        if role != "user":
            return Content(role="user", parts=response.candidates[0].content.parts)
        return Content(role=response.candidates[0].content.role, parts=response.candidates[0].content.parts)
        
    
    