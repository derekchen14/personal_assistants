"""
I am building a real-time chat app where the user can have a conversation about sports. 
My backend API is written in Python with FastAPI and the front-end is written in Svelte. 
I already have a Websockets connection for the chat, and I now what to also stream real time sports scores. 
As a result, my options are 
(a) use existing FastAPI websockets connection for chat and adapt it to also handle sports scores 
(b) add an additional websockets connection for sports scores or 
(c) just use Server-Sent Events (SSE) for the sports scores. 
What is the best option?

To give more details, my existing websockets connection is fairly complicated, so pay attention.
When having a conversation, the agent on the server side goes through three steps:
1a. Determine if a sports team is mentioned in the conversation
1b. Return a signal back to the client side if a sports team is mentioned
2a. Search for the sports team in the database
2b. Return the sports team's information back to the client side
3. Generate a natural language response
Notice that steps 1b, 2b, and 3 all return responses.
In order to handle multiple async responses, we use `queue = asyncio.Queue()`
The goal of adding the new streaming API is to replace the call to the database with a call to a third-party streaming service.
Therefore, I want to transform Step 2b into a streaming service.
As a result, my options are (a) turn the existing websockets connection into a streaming connection or
b) add a Server-side Events (SSE) connection while also removing the response from Step 2b.
"""

webserver - chat()
agent - understand_language()
nlu - predict() > icl.predict_dialog_state()
helper - api.stream_response()


@app.websocket("/ws")
async def chat(websocket: WebSocket):
  await websocket.accept() 

  async def sender():
    while True:
      message = await queue.get()
      await websocket.send_json(message)
  sender_task = asyncio.create_task(sender())

  while True:
    body = await websocket.receive_json()
    status = await asyncio.to_thread(agent.listen, body)

    if len(status.all_scores) > 0:
      await queue.put(status.all_scores)

    response = await asyncio.to_thread(agent.respond, status)
    await queue.put(response)


all_scores = []
for chunk in status.streaming_scores():
  score = chunk[0]['diff']
  if score is not None:
    await queue.put(score)
  all_scores.extend(score)
status.all_scores = all_scores

"""
I am making a python-based chatbot web app with FastAPI on the backend, connected to Svelte front end. Since a chatbot should be real-time, I am using Websockets, imported from FastAPI.
My code in main.py looks like this ```@app.websocket("/ws")
async def chat(websocket: WebSocket):
  await websocket.accept()
  while True:
    body = await websocket.receive_json()
    intent = agent.listen(body)
    task = asyncio.create_task( websocket.send_json(intent) )
    await task
    response = await asyncio.to_thread(agent.execute, intent)
    await websocket.send_json(response)```. 
"""


@app.websocket("/ws")
async def chat(websocket: WebSocket):
  await websocket.accept()
  while True:
    body = await websocket.receive_json()
    intent = agent.listen(body)
    task = asyncio.create_task( websocket.send_json(intent) )
    await task
    response = await asyncio.to_thread(agent.execute, intent)
    await websocket.send_json(response)

"""
  elif len(state.thought) > 0:
    thought_json = build_json_response_for_state(state)
    data_analyst.res.top_panel = thought_json
    await queue.put(thought_json)
    stall_task.cancel()  # Restart the timer with a fresh task
    stall_task = asyncio.create_task(stall_for_time(24))
"""