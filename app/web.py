from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.database import SessionLocal, init_db
from app.models import User, UserSkill, Attempt
from app.services import get_question, calculate_score, level_for_score, load_questions, random_scenario

app = FastAPI(title="TAIGA Survival Bot Web", version="0.1.0")
MODULES = {"fire":"Огонь","water":"Вода","navigation":"Навигация","shelter":"Лагерь","first_aid":"Первая помощь","winter":"Зима"}

class Answer(BaseModel):
    module: str
    question_id: str
    answer: int

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health(): return {"status":"ok"}

@app.get("/api/modules")
async def modules():
    return [{"id":k,"name":v,"questions":len(load_questions(k))} for k,v in MODULES.items()]

@app.get("/api/question/{module}")
async def question(module: str):
    if module not in MODULES: raise HTTPException(404,"Модуль не найден")
    item=get_question(module,2)
    if not item: raise HTTPException(404,"В модуле нет вопросов")
    return {"id":item["id"],"question":item["question"],"options":item["options"]}

@app.post("/api/answer")
async def answer(payload: Answer):
    if payload.module not in MODULES: raise HTTPException(400,"Модуль не найден")
    item=next((q for q in load_questions(payload.module) if q["id"]==payload.question_id),None)
    if not item or not 0<=payload.answer<len(item["options"]): raise HTTPException(400,"Некорректный вопрос или ответ")
    correct=payload.answer==item["answer"]
    async with SessionLocal() as session:
        user=(await session.execute(select(User).where(User.telegram_id==-1))).scalar_one_or_none()
        if not user:
            user=User(telegram_id=-1,username="web_demo",first_name="Web")
            session.add(user); await session.flush()
        skill=(await session.execute(select(UserSkill).where(UserSkill.user_id==user.id,UserSkill.module==payload.module))).scalar_one_or_none()
        if not skill:
            skill=UserSkill(user_id=user.id,module=payload.module); session.add(skill); await session.flush()
        skill.attempts+=1; skill.correct+=int(correct); skill.score=calculate_score(skill.score,correct)
        session.add(Attempt(user_id=user.id,module=payload.module,question_id=payload.question_id,answer=str(payload.answer),is_correct=correct))
        await session.commit(); score=skill.score
    return {"correct":correct,"explanation":item["explanation"],"score":score,"level":level_for_score(score)}

@app.get("/api/profile")
async def profile():
    async with SessionLocal() as session:
        user=(await session.execute(select(User).where(User.telegram_id==-1))).scalar_one_or_none()
        if not user: return {"skills":[],"average":0,"level":"Городской"}
        skills=(await session.execute(select(UserSkill).where(UserSkill.user_id==user.id))).scalars().all()
    avg=sum(s.score for s in skills)/len(skills) if skills else 0
    return {"skills":[{"module":s.module,"name":MODULES.get(s.module,s.module),"score":s.score,"correct":s.correct,"attempts":s.attempts} for s in skills],"average":avg,"level":level_for_score(avg)}

@app.get("/api/scenario")
async def scenario():
    item=random_scenario()
    return {"id":item["id"],"title":item["title"],"text":item["text"],"options":item["options"]}

@app.get("/",response_class=HTMLResponse)
async def index(): return HTMLResponse(INDEX_HTML)

INDEX_HTML='''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TAIGA Survival</title><style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0}main{max-width:900px;margin:auto;padding:24px}.muted{color:#aaa}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.card,button{background:#1d1d1d;border:1px solid #383838;border-radius:12px;color:#eee;padding:16px}.card{cursor:pointer}.card:hover,button:hover{background:#292929}button{cursor:pointer;width:100%;margin:6px 0;text-align:left}.nav{display:flex;gap:8px;margin:20px 0}.nav button{width:auto}.hidden{display:none}.bar{height:10px;background:#333;border-radius:10px;overflow:hidden}.fill{height:100%;background:#ddd}</style></head><body><main><h1>TAIGA Survival</h1><div class="muted">Браузерный тренажёр автономности</div><div class="nav"><button onclick="show('training')">Тренировка</button><button onclick="show('profile');profile()">Профиль</button><button onclick="show('scenario');scenario()">Сценарий ЧС</button></div><section id="training"><h2>Модули</h2><div id="modules" class="grid"></div><div id="quiz"></div></section><section id="profile" class="hidden"><h2>Прогресс</h2><div id="stats"></div></section><section id="scenario" class="hidden"><h2>Сценарий</h2><div id="sc"></div></section></main><script>const $=id=>document.getElementById(id);function show(id){['training','profile','scenario'].forEach(x=>$(x).classList.toggle('hidden',x!==id))}async function loadModules(){let m=await fetch('/api/modules').then(r=>r.json());$('modules').innerHTML=m.map(x=>`<div class="card" onclick="question('${x.id}')"><b>${x.name}</b><div class="muted">${x.questions} вопросов</div></div>`).join('')}async function question(m){let q=await fetch('/api/question/'+m).then(r=>r.json());$('quiz').innerHTML=`<div class="card"><h3>${q.question}</h3>${q.options.map((x,i)=>`<button onclick="answer('${m}','${q.id}',${i})">${x}</button>`).join('')}</div>`}async function answer(m,id,i){let r=await fetch('/api/answer',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({module:m,question_id:id,answer:i})}).then(x=>x.json());$('quiz').innerHTML=`<div class="card"><h3>${r.correct?'Правильно':'Неправильно'}</h3><p>${r.explanation}</p><b>Навык: ${Math.round(r.score)}% — ${r.level}</b><button onclick="question('${m}')">Следующий вопрос</button></div>`}async function profile(){let p=await fetch('/api/profile').then(r=>r.json());$('stats').innerHTML=`<div class="card"><h3>Уровень: ${p.level}</h3><p>Средний навык: ${Math.round(p.average)}%</p>${p.skills.map(s=>`<p><b>${s.name}</b> — ${Math.round(s.score)}% (${s.correct}/${s.attempts})</p><div class="bar"><div class="fill" style="width:${s.score}%"></div></div>`).join('')}</div>`}async function scenario(){let s=await fetch('/api/scenario').then(r=>r.json());$('sc').innerHTML=`<div class="card"><h3>${s.title}</h3><p>${s.text}</p>${s.options.map(x=>`<button onclick="alert('Демо: выбор принят')">${x}</button>`).join('')}</div>`}loadModules();</script></body></html>'''
