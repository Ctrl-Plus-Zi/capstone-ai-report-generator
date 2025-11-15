from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate 
from langchain_core.output_parsers import StrOutputParser 
from langchain.chains.llm import LLMChain 
from langchain.chains.sequential import SequentialChain 
from langchain_openai import ChatOpenAI 
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv


load_dotenv("./backend/.env")

'''
llm = init_chat_model("gpt-4o-mini", 
    model_provider="openai", 
    temperature=0.1, 
    max_tokens=200 
)'''

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7, max_tokens=200)

'''prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 입력을 바탕으로 명언을 만들어주는 전문가야"),
    ("user", "{input}")
])'''

prompt1 = ChatPromptTemplate.from_template(
    "입력을 바탕으로 농담을 만들어줘\n\n{input}" 
)

chain1 = LLMChain(llm=llm, prompt=prompt1, output_key="joke")

prompt2 = ChatPromptTemplate.from_template(
    "이 농담의 센스를 해설해줘\n\n{joke}"  
)

chain2 = LLMChain(llm=llm, prompt=prompt2, output_key="explanation")

all_chain = SequentialChain(
    chains=[chain1, chain2], 
    input_variables=["input"], 
    output_variables=["joke", "explanation"]
)

#output_parser = StrOutputParser()
#chain = prompt | llm | output_parserS
result = all_chain.invoke({"input": "맨날 코딩만 하는데 취업이 어려움"})

print(result)
