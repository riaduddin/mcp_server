import asyncio

from dotenv import load_dotenv
from langchain_groq import ChatGroq

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser


from mcp_use import MCPAgent, MCPClient
import os

async def run_memory_chat():
    """Run a chat using MCPAgent's built-in conversation memory."""
    # Load environment variables for API keys
    load_dotenv()
    os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY","riad")

    # Config file path - change this to your config file
    config_file = "todo.json"

    print("Initializing chat...")

    # Create MCP client and agent with memory enabled
    client = MCPClient.from_config_file(config_file)
    # llm = GoogleGenerativeAI(model="gemini-2.0-pro") | StrOutputParser()
    # # llm = ToolDisabledLLM(raw_llm)
    # setattr(llm, "bind_tools", lambda tools: llm)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")
    # setattr(llm, "bind_tools", lambda tools: llm)
    # llm = llm | StrOutputParser()
    print("Client initialized successfully.")
    print("Creating agent with memory enabled...")
    # Create agent with memory_enabled=True
    agent = MCPAgent(
        llm=llm,
        client=client,
        max_steps=15,
        memory_enabled=True,
    )

    print("\n===== Interactive MCP Chat =====")
    print("Type 'exit' or 'quit' to end the conversation")
    print("Type 'clear' to clear conversation history")
    print("==================================\n")

    try:
        # Main chat loop
        while True:
            # Get user input
            user_input = input("\nYou: ")

            # Check for exit command
            if user_input.lower() in ["exit", "quit"]:
                print("Ending conversation...")
                break

            # Check for clear history command
            if user_input.lower() == "clear":
                agent.clear_conversation_history()
                print("Conversation history cleared.")
                continue

            # Get response from agent
            print("\nAssistant: ", end="", flush=True)

            try:
                # Run the agent with the user input (memory handling is automatic)
                response = await agent.run(user_input)
                print(response)

            except Exception as e:
                print(f"\nError: {e}")

    finally:
        # Clean up
        if client and client.sessions:
            await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(run_memory_chat())