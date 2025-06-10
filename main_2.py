from mcp.server.fastmcp import FastMCP
from typing import Optional
import httpx
from langchain_groq import ChatGroq
from mcp.server.fastmcp.prompts import base
import os

from langchain_google_genai import GoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser


mcp = FastMCP(
    name="TodoApp",
    host="0.0.0.0",  # only used for SSE transport (localhost)
    port=8050,  # only used for SSE transport (set this to any port)
)



from dotenv import load_dotenv
load_dotenv()

from typing import Optional
import httpx

@mcp.prompt()
def suggest_task_prompt(title: str, description: str) -> list[base.Message]:
    return [
        base.UserMessage("I'd like you to review a task I'm working on."),
        base.UserMessage(f"Title: {title}"),
        base.UserMessage(f"Description: {description or '(none)'}"),
        base.AssistantMessage("Thanks. Let me suggest some improvements."),
    ]
    

@mcp.tool()
def get_tasks_for_user(username: str, password: str) -> list:
    """Return all tasks for a user in the backend-defined order."""
    login = httpx.post("http://localhost:8000/api/token/", json={"username": username, "password": password})
    if login.status_code != 200:
        return ["❌ Login failed."]
    
    token = login.json().get("access")
    if not token:
        return ["❌ No token received."]

    response = httpx.get("http://localhost:8000/api/tasks/", headers={
        "Authorization": f"Bearer {token}"
    })
    
    if response.status_code == 200:
        return response.json()
    else:
        return [f"❌ Failed to get tasks: {response.status_code}"]

@mcp.tool()
def suggest_task_improvements(username: str, password: str, position: int) -> str | list:
    """
    Review a task by its position and suggest improvements to title or description.
    """
    login = httpx.post("http://localhost:8000/api/token/", json={"username": username, "password": password})
    if login.status_code != 200:
        return "❌ Login failed."

    token = login.json().get("access")
    if not token:
        return "❌ No token received."

    task_list = httpx.get("http://localhost:8000/api/tasks/", headers={
        "Authorization": f"Bearer {token}"
    }).json()

    if len(task_list) < position:
        return f"⚠️ You only have {len(task_list)} task(s). Can't find task at position {position}."

    task = task_list[position - 1]
    title = task["title"]
    desc = task.get("description", "")

    # Use LLM via langchain to evaluate quality
    messages = suggest_task_prompt(task["title"], task.get("description"))
    #tuple_messages = [("human", m.content) for m in messages]
    os.environ["GOOGLE_API_KEY"]=os.getenv("GOOGLE_API_KEY","riad")
    llm = GoogleGenerativeAI(model="gemini-2.0-pro")
    #llm = ToolDisabledLLM(raw_llm)
    return llm.invoke(messages)

@mcp.tool()
def delete_task_by_position(username: str, password: str, position: int) -> str:
    """Delete a task at a specific position in the list (1-based)."""
    login = httpx.post("http://localhost:8000/api/token/", json={"username": username, "password": password})
    if login.status_code != 200:
        return "❌ Login failed."

    token = login.json().get("access")
    if not token:
        return "❌ No token."

    task_list = httpx.get("http://localhost:8000/api/tasks/", headers={
        "Authorization": f"Bearer {token}"
    }).json()

    if len(task_list) < position:
        return f"⚠️ Only {len(task_list)} tasks. Cannot find task #{position}."

    task_id = task_list[position - 1]["id"]
    response = httpx.delete(
        f"http://localhost:8000/api/tasks/{task_id}/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if response.status_code == 204:
        return f"🗑️ Task #{position} deleted."
    return f"❌ Delete failed: {response.status_code} - {response.text}"


@mcp.tool()
def update_task_by_title(
    username: str,
    password: str,
    title: str,
    new_title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    completed: Optional[bool] = None
) -> str:
    """
    Update a task using its title instead of task ID. Matches the first task found with that title.
    """
    # Login for token
    login_response = httpx.post("http://localhost:8000/api/token/", json={
        "username": username,
        "password": password
    })
    if login_response.status_code != 200:
        return "❌ Login failed."

    token = login_response.json().get("access")
    if not token:
        return "❌ Login succeeded but token not returned."

    # Get all tasks for the user
    task_list_response = httpx.get(
        "http://localhost:8000/api/tasks/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if task_list_response.status_code != 200:
        return "❌ Failed to fetch tasks."

    tasks = task_list_response.json()
    task = next((t for t in tasks if t["title"].strip().lower() == title.strip().lower()), None)

    if not task:
        return f"❌ No task found with title '{title}'."

    task_id = task["id"]

    update_data = {
        "title": new_title or task["title"],
        "description": description or task.get("description"),
        "due_date": due_date or task.get("due_date"),
        "completed": completed if completed is not None else task.get("completed"),
    }

    response = httpx.put(
        f"http://localhost:8000/api/tasks/{task_id}/",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data
    )

    if response.status_code == 200:
        return f"✅ Task '{title}' updated successfully."
    return f"❌ Update failed: {response.status_code} - {response.text}"


@mcp.tool()
def update_task_for_user(
    username: str,
    password: str,
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    completed: Optional[bool] = None
) -> str:
    """
    Logs in with username and password, then updates the given task ID.
    Only provide the fields you want to update.
    """
    login_response = httpx.post("http://localhost:8000/api/token/", json={
        "username": username,
        "password": password
    })

    if login_response.status_code != 200:
        return "❌ Login failed. Please check your credentials."

    token = login_response.json().get("access")
    if not token:
        return "❌ Login succeeded but token was not returned."

    update_data = {
        "title": title,
        "description": description,
        "due_date": due_date,
        "completed": completed
    }
    # Remove None values
    update_data = {k: v for k, v in update_data.items() if v is not None}

    if not update_data:
        return "⚠️ No update fields provided."

    response = httpx.put(
        f"http://localhost:8000/api/tasks/{task_id}/",
        headers={"Authorization": f"Bearer {token}"},
        json=update_data
    )

    if response.status_code == 200:
        return f"✅ Task {task_id} updated successfully."
    return f"❌ Failed to update task {task_id}: {response.status_code} - {response.text}"


@mcp.tool()
def delete_task_by_title(
    username: str,
    password: str,
    title: str
) -> str:
    """
    Delete the user's task by its title (case-insensitive match).
    """
    # Login
    login_response = httpx.post("http://localhost:8000/api/token/", json={
        "username": username,
        "password": password
    })
    if login_response.status_code != 200:
        return "❌ Login failed."

    token = login_response.json().get("access")
    if not token:
        return "❌ Token not received."

    # Get task list
    task_list_response = httpx.get(
        "http://localhost:8000/api/tasks/",
        headers={"Authorization": f"Bearer {token}"}
    )
    if task_list_response.status_code != 200:
        return "❌ Failed to fetch tasks."

    tasks = task_list_response.json()
    task = next((t for t in tasks if t["title"].strip().lower() == title.strip().lower()), None)

    if not task:
        return f"❌ No task found with title '{title}'."

    task_id = task["id"]

    # Delete
    response = httpx.delete(
        f"http://localhost:8000/api/tasks/{task_id}/",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 204:
        return f"🗑️ Task '{title}' deleted."
    return f"❌ Failed to delete: {response.status_code} - {response.text}"

@mcp.tool()
def delete_task_for_user(
    username: str,
    password: str,
    task_id: int
) -> str:
    """
    Logs in with username and password, then deletes the task with the given ID.
    """
    login_response = httpx.post("http://localhost:8000/api/token/", json={
        "username": username,
        "password": password
    })

    if login_response.status_code != 200:
        return "❌ Login failed. Please check your credentials."

    token = login_response.json().get("access")
    if not token:
        return "❌ Login succeeded but token was not returned."

    response = httpx.delete(
        f"http://localhost:8000/api/tasks/{task_id}/",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 204:
        return f"🗑️ Task {task_id} deleted successfully."
    return f"❌ Failed to delete task {task_id}: {response.status_code} - {response.text}"


@mcp.tool()
def add_task_for_user(
    username: str,
    password: str,
    title: str,
    description: Optional[str] = None,
    due_date: Optional[str] = None
) -> str:
    """
    Logs in with the given username and password, then creates a task on behalf of the user.
    """

    # 🔐 Step 1: Login and get token
    login_url = "http://localhost:8000/api/token/"
    login_data = {"username": username, "password": password}
    login_response = httpx.post(login_url, json=login_data)

    if login_response.status_code != 200:
        return "❌ Login failed. Please check your username and password."

    token = login_response.json().get("access")  # For JWT
    if not token:
        return "❌ Login succeeded but token not found."

    # ✅ Step 2: Create task
    task_url = "http://localhost:8000/api/tasks/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    task_data = {
        "title": title,
        "description": description,
        "due_date": due_date
    }

    task_response = httpx.post(task_url, json=task_data, headers=headers)

    if task_response.status_code == 201:
        return f"✅ Task '{title}' created for {username}."
    else:
        return f"❌ Failed to create task: {task_response.status_code} - {task_response.text}"
    
    
    
if __name__ == "__main__":
    transport = "sse"
    if transport == "stdio":
        print("Running server with stdio transport")
        mcp.run(transport="stdio")
    elif transport == "sse":
        print("Running server with SSE transport")
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Unknown transport: {transport}")