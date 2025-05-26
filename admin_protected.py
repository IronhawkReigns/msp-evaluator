from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi_login import LoginManager
from pydantic import BaseModel
import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecret")
manager = LoginManager(SECRET_KEY, token_url="/auth/login", use_cookie=True)
manager.cookie_name = "admin_token"
manager.cookie_secure = True
manager.cookie_samesite = "lax"

# Simple user data model
class User(BaseModel):
    name: str

# Temporary in-memory user store
fake_users = {
    "admin": {"name": "admin", "password": "password123"}
}

@manager.user_loader
def load_user(username: str):
    print(f"✅ load_user invoked for: {username}")
    user = fake_users.get(username)
    if user:
        return User(name=user["name"])

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/auth/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    next_url = request.query_params.get("next", "/admin")

    print(f"🚨 Login attempt: username={username}, password={password}")

    user = fake_users.get(username)
    if not user or user["password"] != password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key=manager.cookie_name,
        value=manager.create_access_token(data={"sub": user["name"]}),
        httponly=True,
        secure=True,
        samesite="lax"
    )
    # manager.set_cookie(response, user["name"])
    return response

@router.get("/admin")
def admin_dashboard(request: Request, user=Depends(manager)):
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

@router.get("/logout")
def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(manager.cookie_name)
    return response

@router.delete("/ui/delete_company/{company_name}")
def delete_company(company_name: str, user=Depends(manager)):
    from api_server import collection
    results = collection.get(where={"msp_name": company_name})
    ids_to_delete = results["ids"]
    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
    return {"status": "deleted", "count": len(ids_to_delete)}

@router.delete("/ui/delete/{entry_id}")
def delete_entry(entry_id: str, user=Depends(manager)):
    from api_server import collection
    collection.delete(ids=[entry_id])
    return {"status": "success"}

@router.get("/auth/check")
def check_auth(user=Depends(manager)):
    return {"status": "ok"}


# Debug route to show current authenticated user
@router.get("/whoami")
def whoami(user=Depends(manager)):
    return {"user": user.name}

print("✅ admin_protected: user_loader callback registered:", load_user)
