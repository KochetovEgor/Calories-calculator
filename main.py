import psycopg2
from fastapi import FastAPI, Cookie, Form, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from psycopg2 import pool


class DBconnect:
    def __init__(self, new_pool):
        self.__pool = new_pool

    def __enter__(self):
        self.__conn = self.__pool.getconn()
        return self.__conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__pool.putconn(self.__conn)
        return False


db_pool = pool.SimpleConnectionPool(
    minconn=1,
    maxconn=2,
    user="postgres",
    password="loloegordeezbender12",
    host="localhost",
    port=5432,
    database="Calories Database"
)

app = FastAPI()

templates = Jinja2Templates(directory="templates")

@app.get("/")
def read_root(request: Request , username: str | None = Cookie(None)):
    if username is None:
        return RedirectResponse("/login")
    return templates.TemplateResponse(request=request, name="main.html", context={"username": username})

@app.get("/login")
def get_login():
    return FileResponse("templates/login.html")

@app.post("/login")
def post_login(username: str | None = Form(None),
               password: str | None = Form(None)):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id FROM users
            WHERE username = %s and password = %s''', (username, password))
            if cur.fetchone() is None:
                return RedirectResponse("/login", status_code=302)
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(key="username", value=username)
    return response

@app.post("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(key="username")
    return response

@app.get("/registration")
def get_registration(request: Request, error: str =""):
    return templates.TemplateResponse(request=request, name="registration.html",
                                      context={"error": error})

@app.post("/registration")
def post_registration(username: str | None = Form(None),
                      password_1: str | None = Form(None),
                      password_2: str | None = Form(None)):
    if password_1 != password_2:
        error = "Пароли должны совпадать"
        return RedirectResponse(url=f"/registration?error={error}", status_code=302)
    try:
        with DBconnect(db_pool) as conn:
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO users (username, password) VALUES (%s, %s)''', (username, password_1))
                conn.commit()
    except psycopg2.errors.UniqueViolation as e:
        error = "Пользователь с таким именем уже существует"
        return RedirectResponse(url=f"/registration?error={error}", status_code=302)
    except Exception as e:
        error = 'Неизвестная ошибка'
        return RedirectResponse(url=f"/registration?error={error}", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/food")
def get_food(request: Request, error: str = ""):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT name, base_weight, calories,
            proteins, fats, carbohydrates
            FROM food''')
            food=cur.fetchall()
    return templates.TemplateResponse(request=request, name="food.html", context={"food": food, "error": error})

@app.post("/food/add")
def add_food(name: str = Form(),
             base_weight: int = Form(),
             calories: float = Form(),
             proteins: float = Form(),
             fats: float = Form(),
             carbohydrates: float = Form()):
    try:
        with DBconnect(db_pool) as conn:
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO 
                food (name, base_weight, calories, proteins, fats, carbohydrates)
                VALUES (%s, %s, %s, %s, %s, %s)''',
                            (name, base_weight, calories, proteins, fats, carbohydrates))
                conn.commit()
    except psycopg2.errors.UniqueViolation as e:
        error = 'Еда с таким названием уже существует'
        return RedirectResponse(url=f"/food?error={error}", status_code=302)
    return RedirectResponse(url="/food", status_code=302)

@app.on_event("shutdown")
def on_shutdown():
    if db_pool:
        db_pool.closeall()

@app.get("/test")
def test():
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM users")
            return cur.fetchall()