from fastapi import FastAPI,Request

app = FastAPI()


@app.post("/")
async def root(request: Request):
    data = await request.form()
    