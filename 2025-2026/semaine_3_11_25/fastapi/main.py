from fastapi import FastAPI , Depends , HTTPException
from sqlalchemy.orm import Session
from bdd.database import Base , engine , SessionLocal
from bdd.models import Todo

app = FastAPI ( title = " FastAPI Todo Challenge " )

# C r a t i o n automatique de la base
Base . metadata . create_all ( bind = engine )

# D p e n d a n c e de session
def get_db () :
    db = SessionLocal ()
    try :
        yield db
    finally :
        db . close ()

@app . get ( "/" )
def home () :
    return { " message " : " Bienvenue dans le TP FastAPI - Todo API " }


# 1 Lire toutes les t c h e s
@app . get ("/todos")
def read_todos ( db : Session = Depends ( get_db ) ) :
    return db . query ( Todo ) . all ()

# 2 C r e r une nouvelle t c h e
@app . post ("/todos")
def create_todo ( title : str , description : str = " " , db : Session = Depends( get_db ) ) :
    todo = Todo ( title = title , description = description )
    db . add ( todo )
    db . commit ()
    db . refresh ( todo )
    return todo

# 3 Mettre jour une t c h e
@app . put ("/todos/{todo_id}")
def update_todo ( todo_id : int , completed : bool , db : Session = Depends (get_db ) ) :
    todo = db . query ( Todo ) . filter ( Todo . id == todo_id ) . first ()
    if not todo :
        raise HTTPException ( status_code =404 , detail = " T c h e non t r o u v e" )
    todo . completed = completed
    db . commit ()
    db . refresh ( todo )
    return todo

# 4 Supprimer une t c h e
@app . delete ("/todos/{todo_id}")
def delete_todo ( todo_id : int , db : Session = Depends ( get_db ) ) :
    todo = db . query ( Todo ) . filter ( Todo . id == todo_id ) . first ()
    if not todo :
        raise HTTPException ( status_code =404 , detail = " T c h e non t r o u v e" )
    db . delete ( todo )
    db . commit ()
    return { "message " : " T c h e s u p p r i m e " }


