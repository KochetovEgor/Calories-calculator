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
    password="",
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
    except psycopg2.errors.UniqueViolation:
        error = "Пользователь с таким именем уже существует"
        return RedirectResponse(url=f"/registration?error={error}", status_code=302)
    except:
        error = 'Неизвестная ошибка'
        return RedirectResponse(url=f"/registration?error={error}", status_code=302)
    return RedirectResponse(url="/login", status_code=302)

@app.get("/food")
def get_food(request: Request, error: str = "",
             username: str | None = Cookie(None)):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT
                            name, base_weight, calories, proteins, fats, carbohydrates
                        FROM
                            food AS f JOIN users AS u ON f.user_id = u.id
                        WHERE u.username = %s
                        UNION SELECT name, base_weight, calories, proteins, fats, carbohydrates
                        FROM food
                        WHERE user_id = 1''', (username,))
            food=cur.fetchall()
    return templates.TemplateResponse(request=request, name="food.html", context={"food": food, "error": error})

@app.post("/food/add")
def add_food(name: str = Form(),
             base_weight: int = Form(),
             calories: float = Form(),
             proteins: float = Form(),
             fats: float = Form(),
             carbohydrates: float = Form(),
             username: str | None = Cookie(None)):
    try:
        with DBconnect(db_pool) as conn:
            with conn.cursor() as cur:
                cur.execute('''INSERT INTO 
                food (user_id, name, base_weight, calories, proteins, fats, carbohydrates)
                SELECT users.id, %s, %s, %s, %s, %s, %s
                FROM users WHERE username = %s''',
                            (name, base_weight, calories, proteins, fats, carbohydrates, username))
                conn.commit()
    except psycopg2.errors.UniqueViolation:
        error = 'Еда с таким названием уже существует'
        return RedirectResponse(url=f"/food?error={error}", status_code=302)
    return RedirectResponse(url="/food", status_code=302)

@app.get("/statistics")
def get_statistics(request: Request,
                   username: str | None = Cookie(None),
                   msg: str = ""):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT date, calories, proteins, fats, carbohydrates
            FROM statistics JOIN users ON statistics.user_id = users.id
            WHERE username =  %s
            ORDER BY date DESC''',
                        (username,))
            date = cur.fetchall()
    return templates.TemplateResponse(request=request, name="statistics.html",
                                      context={"date": date, "msg": msg})

@app.get("/statistics/detailed/{date}")
def get_statistics_for_date(date: str,
                            request: Request,
                            username: str | None = Cookie(None)):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT
                            name,
                            f_s.weight,
                            ROUND(f.calories * f_s.weight / f.base_weight, 2),
                            ROUND(f.proteins * f_s.weight / f.base_weight, 2),
                            ROUND(f.fats * f_s.weight / f.base_weight, 2),
                            ROUND(f.carbohydrates * f_s.weight / f.base_weight, 2)
                        FROM
                            food AS f
                            JOIN food_statistics AS f_s ON f.id = f_s.food_id
                            JOIN statistics AS s ON f_s.statistics_id = s.id
                            JOIN users AS u on s.user_id = u.id
                        WHERE s.date = %s AND u.username = %s
            ''', (date, username,))
            food = cur.fetchall()
            cur.execute('''SELECT
                            calories, proteins, fats, carbohydrates
                        FROM
                            statistics AS s JOIN users AS u ON s.user_id = u.id
                        WHERE s.date = %s AND u.username = %s
                        ''', (date, username,))
            sum_food = cur.fetchall()[0]
    return templates.TemplateResponse(request=request, name="statistics_for_day.html",
                                      context={"food": food, "date": date, "sum_food": sum_food})

@app.post("/statistics/detailed/{date}/delete")
def delete_statistics_for_date(date: str,
                               request: Request,
                               username: str | None = Cookie(None)):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''DELETE FROM statistics
             WHERE date = %s AND user_id = (SELECT
             id FROM users
             WHERE username = %s)''', (date,username))
            conn.commit()
    msg = "Данные успешно удалены"
    return RedirectResponse(url=f"/statistics?msg={msg}", status_code=302)

@app.get("/statistics/add")
def get_statistics_add(request: Request,
                       username: str | None = Cookie(None),
                       error:str = ""):
    with DBconnect(db_pool) as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT
                            f.id, name, base_weight, calories, proteins, fats, carbohydrates
                        FROM
                            food AS f JOIN users AS u ON f.user_id = u.id
                        WHERE u.username = %s
                        UNION SELECT id, name, base_weight, calories, proteins, fats, carbohydrates
                        FROM food
                        WHERE user_id = 1''', (username,))
            food = cur.fetchall()
    return templates.TemplateResponse(request=request, name="statistics_add.html",
                                      context={"food": food, "error": error})

@app.post("/statistics/add")
async def add_statistics(request: Request,
                   username: str | None = Cookie(None)
                   ):
    form = await request.form()
    date = ''
    dishes = {}
    s_id = 0
    for key, value in form.items():
        if value:
            if key == 'date':
                date = value
            else:
                dishes[int(key)] = float(value)
    try:
        with DBconnect(db_pool) as conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT 
                        id, base_weight, calories, proteins, fats, carbohydrates
                        FROM food
                        WHERE id = ANY(%s)
                ''', (list(dishes.keys()),))
                calories = cur.fetchall()
                sum_calories = [0, 0, 0, 0]
                for dish in calories:
                    for index, val in enumerate(sum_calories):
                        sum_calories[index] += float(dish[index + 2]) * dishes[dish[0]] / dish[1]
                cur.execute('''INSERT INTO statistics (user_id, date, calories, proteins, fats, carbohydrates)
                                SELECT
                                    id, %s, %s, %s, %s, %s
                                FROM users as u
                                WHERE u.username = %s
                                ''', (date, sum_calories[0],
                                      sum_calories[1], sum_calories[2],
                                      sum_calories[3], username))
                conn.commit()
                cur.execute('''SELECT s.id FROM
                            statistics AS s JOIN users AS u ON s.user_id = u.id
                            WHERE s.date = %s AND u.username = %s''', (date, username))
                s_id = int(cur.fetchall()[0][0])
                for_add_food_statistics = [(key, s_id, value) for key, value in dishes.items()]
                cur.executemany('''INSERT INTO food_statistics 
                            (food_id, statistics_id, weight)
                            VALUES (%s, %s, %s)''', for_add_food_statistics)
                conn.commit()
                msg = "Данные успешно добавлены"
    except psycopg2.errors.UniqueViolation:
        error = "Данные за эту дату уже существуют"
        RedirectResponse(url=f"/statistics/add?error={error}", status_code=302)
    except:
        error = "Неизвестная ошибка"
        RedirectResponse(url=f"/statistics/add?error={error}", status_code=302)
    return RedirectResponse(url=f"/statistics?msg={msg}", status_code=302)
