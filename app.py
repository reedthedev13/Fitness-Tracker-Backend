from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import date
from typing import List, Optional
import sqlite3
from contextlib import contextmanager
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://fitness-tracker-backend-u559.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = "fitness.db"


def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                date TEXT NOT NULL,
                reps INTEGER NOT NULL,
                sets INTEGER NOT NULL,
                weight REAL
            )
        """)
        conn.commit()


@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


class Workouts(BaseModel):
    type: str
    date: date
    reps: int
    sets: int
    weight: Optional[float] = None


class WorkoutResponse(Workouts):
    id: int


class AnalyticsResponse(BaseModel):
    labels: List[str]
    reps_data: List[int]
    volume_data: List[float]


init_db()


@app.post("/workouts/", response_model=WorkoutResponse)
async def add_workout(workout: Workouts):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO workouts (type, date, reps, sets, weight)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    workout.type,
                    workout.date.isoformat(),
                    workout.reps,
                    workout.sets,
                    workout.weight,
                ),
            )
            conn.commit()

            cursor.execute("""
                SELECT id, type, date, reps, sets, weight 
                FROM workouts 
                WHERE id = last_insert_rowid()
            """)
            new_workout = cursor.fetchone()

            return {
                "id": new_workout[0],
                "type": new_workout[1],
                "date": new_workout[2],
                "reps": new_workout[3],
                "sets": new_workout[4],
                "weight": new_workout[5],
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workouts/", response_model=List[WorkoutResponse])
async def get_workouts():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, type, date, reps, sets, weight 
                FROM workouts 
                ORDER BY date DESC
            """)
            return [
                {
                    "id": row[0],
                    "type": row[1],
                    "date": row[2],
                    "reps": row[3],
                    "sets": row[4],
                    "weight": row[5],
                }
                for row in cursor.fetchall()
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics/", response_model=AnalyticsResponse)
async def get_analytics():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT type, 
                       SUM(reps * sets) as total_reps,
                       SUM(reps * sets * COALESCE(weight, 1)) as total_volume
                FROM workouts
                WHERE date >= date('now', '-7 days', 'localtime')
                GROUP BY type
            """)
            results = cursor.fetchall()
            return {
                "labels": [row[0] for row in results],
                "reps_data": [row[1] for row in results],
                "volume_data": [row[2] for row in results],
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/workouts/{workout_id}")
async def delete_workout(workout_id: int):
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id FROM workouts WHERE id = ?", (workout_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Workout not found")
            cursor.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
            conn.commit()
            return {"status": "success", "message": "Workout deleted"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
