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

@manager.user_loader
def load_user(username: str):
    env_username = os.getenv("ADMIN_USERNAME")
    if username == env_username:
        return User(name=username)

manager._user_callback = load_user
print("✅ user_loader registration:", getattr(manager, "_user_callback", None))

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.post("/auth/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    next_url = request.query_params.get("next", "/admin")

    print(f"🚨 Login attempt: username={username}, password={password}")
    env_username = os.getenv("ADMIN_USERNAME")
    env_password = os.getenv("ADMIN_PASSWORD")
    
    if username != env_username or password != env_password:
        # Check if request came from English login page
        referer = request.headers.get("referer", "")
        if "/en/login" in referer:
            return RedirectResponse(url="/en/login?error=invalid", status_code=303)
        else:
            return RedirectResponse(url="/login?error=invalid", status_code=303)
    
    # SUCCESS: Always redirect to next_url (which will be /admin)
    response = RedirectResponse(url=next_url, status_code=302)
    response.set_cookie(
        key=manager.cookie_name,
        value=manager.create_access_token(data={"sub": env_username}),
        httponly=True,
        secure=True,
        samesite="lax"
    )
    return response

# ADD this new route for English login page
@router.get("/en/login")
def english_login_page(request: Request):
    return templates.TemplateResponse("en/login.html", {"request": request})

@router.get("/login")
def korean_login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/admin")
def admin_dashboard(request: Request, user=Depends(manager)):
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})

@router.get("/logout")
def logout(request: Request):
    # Detect if user came from English site
    referer = request.headers.get("referer", "")
    redirect_url = "/en" if "/en/" in referer else "/"
    
    response = RedirectResponse(url=redirect_url, status_code=302)
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
def check_auth(request: Request):
    token = request.cookies.get(manager.cookie_name)
    if not token:
        return {"status": "anonymous"}
    try:
        user = manager.get_current_user(token)
        return {"status": "ok", "user": user.name}
    except Exception:
        return {"status": "anonymous"}


# Debug route to show current authenticated user
@router.get("/whoami")
def whoami(user=Depends(manager)):
    return {"user": user.name}

print("✅ admin_protected: user_loader callback registered:", load_user)
