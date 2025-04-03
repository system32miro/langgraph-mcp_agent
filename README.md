# LangGraph Multi-Agent (ReAct + CodeAct) with MCP Tools

This project implements an intelligent agent built using LangGraph, leveraging Anthropic's Claude 3.5 Sonnet model. The core feature is its ability to dynamically choose between a ReAct agent and a CodeAct agent based on task complexity, enabling efficient and robust task execution. It integrates with external tools via the Multi-Process Communication (MCP) protocol.

## Key Features

-   **Dual Agent Architecture:**
    -   A `supervisor` node analyzes the user's request and routes it to the appropriate agent.
    -   **ReAct Agent:** Handles simple tasks typically requiring a single tool invocation. It uses the LLM's tool-calling capabilities to determine arguments and execute the tool.
    -   **CodeAct Agent:** Tackles complex tasks involving multiple tools, data manipulation, or custom logic. It prompts the LLM to generate Python code (an `async def main()` function) that utilizes the available tools (`await tool.ainvoke({...})`) to solve the task.
-   **Asynchronous Execution:** The entire agent graph and tool executions (CodeAct) run asynchronously using `asyncio`, ensuring efficient handling of I/O-bound operations like API calls.
-   **MCP Tool Integration:** Seamlessly connects to and utilizes external tools running as separate processes via the `langchain-mcp-adapters` library. Currently integrated tools:
    -   **Weather Service:** (`get_weather`) Fetches weather information (requires OpenWeather API key).
    -   **Math Operations:** (`add`, `multiply`) Performs basic arithmetic.
    -   **SQLite Database:** (`list_tables`, `describe_table`, `read_query`, `write_query`) Interacts with a SQLite database (e.g., `travel.sqlite`).
-   **LLM Agnostic (Conceptually):** While currently configured for Anthropic Claude 3.5 Sonnet, the core LangGraph structure can be adapted for other compatible language models (like Gemini, which was used previously).
-   **Robust Code Execution:** The `CodeAct` agent uses an `async` sandbox function (`unsafe_eval_for_test`) specifically designed to execute the LLM-generated asynchronous code within the running `asyncio` event loop.
-   **Error Handling & Retries:** Includes basic rate limit handling (exponential backoff) for LLM calls in the final response generation step.

## Architecture Overview

1.  **Input:** User provides a task description.
2.  **Supervisor Node:**
    -   Receives the task.
    -   Uses a mock "BigTool" (`simplified_retrieve_tools`) to identify potentially relevant tools based on keywords.
    -   Determines the complexity based on keywords and the number of tools retrieved.
    -   Routes to either `react_agent` or `codeact_agent`.
3.  **Agent Nodes:**
    -   **`react_agent`:** If chosen, uses LLM tool calling to select arguments for the *single* retrieved tool and invokes it (`await tool.ainvoke(args)`).
    -   **`codeact_agent`:** If chosen, constructs a detailed system prompt (including tool descriptions and examples using `await tool.ainvoke({...})` with dictionary arguments), prompts the LLM to generate an `async def main():` Python script, and executes this script using the `async def unsafe_eval_for_test` function.
4.  **`unsafe_eval_for_test` (CodeAct Only):**
    -   Executes the LLM-generated code using `exec()`.
    -   If an `async def main()` is defined, it `await`s its execution directly within the current event loop.
    -   Captures `stdout` and any globally defined `final_output` variable.
5.  **`final_answer` Node:**
    -   Receives the outcome from the executed agent (either direct tool result or `final_output`/`stdout` from CodeAct).
    -   If necessary (i.e., the last message isn't already a satisfactory AI response), prompts the LLM to generate a user-friendly summary based on the gathered information and the conversation history.
    -   Includes retry logic for rate limits during this final LLM call.
6.  **Output:** Presents the final response to the user.

## Requirements

-   Python 3.9+
-   Anthropic API Key (for Claude 3.5 Sonnet)
-   OpenWeather API Key (for the weather MCP server)
-   Required Python packages (see `requirements.txt` or setup below)

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd langgraph-agent
    ```

2.  **Create and Activate a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    A `requirements.txt` file is provided with the following dependencies:
    ```txt
    langchain-core>=0.1.0
    langgraph>=0.0.20
    langchain-anthropic>=0.1.1
    python-dotenv>=1.0.0
    pydantic>=2.0.0
    langchain-mcp-adapters>=0.0.1
    ```
    Install with:
    ```bash
    pip install -r requirements.txt
    ```
    *Note:* `langchain-mcp-adapters` might need to be installed directly from its source if not yet on PyPI.

4.  **Create Environment File:**
    Create a file named `.env` in the project root and add your API keys:
    ```dotenv
    ANTHROPIC_API_KEY=your_anthropic_api_key_here
    OPENWEATHER_API_KEY=your_openweather_api_key_here
    # Add GEMINI_API_KEY if you switch back or use it elsewhere
    # GEMINI_API_KEY=your_gemini_api_key_here
    ```

5.  **Ensure MCP Servers are Present:**
    The code expects MCP server scripts (`math_server.py`, `weather_server.py`, `sqlite_server.py`) inside an `mcp-servers/` subdirectory relative to `implementation.py`. Make sure these files exist and are executable.

6.  **Ensure Data Files are Present:**
    The code expects the SQLite database (`travel.sqlite`) inside a `data/` subdirectory relative to `implementation.py`. If it doesn't exist, the directory will be created, but database operations might fail.

## Project Structure

- `implementation.py`: Main agent implementation
- `stub.py`: CustomAgent stub for LangGraph integration
- `spec.yml`: Agent specification
- `mcp-servers/`: MCP servers for specific tools
- `data/`: Database and other resources

## Usage

Run the agent with:

```bash
python implementation.py
```

The system will automatically execute test examples with different scenarios.

## Example Queries

- "What's the weather in Lisbon?"
- "What's the weather in Porto and calculate the sum of 10 and 5?"
- "List the tables in the travel database"

## License

[MIT](LICENSE)

## Contributions

Contributions are welcome! Please feel free to submit a Pull Request. 