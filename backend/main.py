import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

MONGO_URL=os.getenv('MONGO_URL','mongodb://localhost:27017'); DB_NAME=os.getenv('DATABASE_NAME','luvtrader')
JWT_SECRET=os.getenv('JWT_SECRET','dev-secret'); EMAIL_MODE=os.getenv('EMAIL_MODE','preview')
ALGO='HS256'; pwd=CryptContext(schemes=['bcrypt'], deprecated='auto'); oauth2=OAuth2PasswordBearer(tokenUrl='/api/auth/login')
app=FastAPI(title='LUVTrader API')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','*').split(','), allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
client=AsyncIOMotorClient(MONGO_URL); db=client[DB_NAME]

class Role(str,Enum): admin='admin'; operations='operations'; client='client'
class ClientStatus(str,Enum): active='active'; paused='paused'; single_month='single month'; TAP='TAP'; TAP_retainer='TAP retainer'; assisted='assisted'; cancelled='cancelled'
class TripStatus(str,Enum): active='active'; sold='sold'; cancelled='cancelled'
class UserIn(BaseModel): name:str; email:EmailStr; role:Role; linked_client_id:Optional[str]=None; password:str='password123'
class ClientIn(BaseModel):
    employee_number:str=''; base:str=''; cwa_name:str; legal_name:str; email:EmailStr; phone:str=''
    paypal:str=''; venmo:str=''; zelle:str=''; payment_notes:str=''; posting_notes:str=''; rotation_group:str='A'
    monthly_estimate:float=0; amount_paid:float=0; rt_month:Optional[str]=None; reactivation_month:Optional[str]=None
    subscription_type:str='premium $250'; client_status:ClientStatus=ClientStatus.active; internal_notes:str=''; admin_flags:list[str]=Field(default_factory=list)
class TripIn(BaseModel): client_id:str; trip_date:str; trip_type:str='3-day'; status:TripStatus=TripStatus.active; sale_amount:float=0; notes:str=''
class MessageIn(BaseModel): client_id:str; message_type:str; subject:str; body:str; preview_before_send:bool=True
class SettingsIn(BaseModel): payment_instructions:dict[str,str]; email_templates:dict[str,dict[str,str]]; instant_send_toggles:dict[str,bool]; tap_settings:dict[str,Any]; global_business_settings:dict[str,Any]

def now(): return datetime.now(timezone.utc).isoformat()
def oid(): return str(uuid4())
def calc(c):
    sold=float(c.get('sold_total',0)); bal=float(c.get('monthly_estimate',0))-float(c.get('amount_paid',0))-sold
    c['balance']=round(bal,2); c['credit_refund_amount']=round(abs(bal),2) if bal<0 else 0; return c
def public(doc):
    if not doc: return doc
    doc=dict(doc); doc.pop('_id',None); doc.pop('password_hash',None); return doc
async def settings():
    s=await db.settings.find_one({'id':'global'})
    if not s:
        s={'id':'global','payment_instructions':{'Venmo':'@LUVTrader','PayPal':'billing@luvtrader.com','Zelle':'billing@luvtrader.com'},'email_templates':DEFAULT_TEMPLATES,'instant_send_toggles':{k:False for k in DEFAULT_TEMPLATES},'tap_settings':{'reactivate_on_month_start':True},'global_business_settings':{'portal_url':'clients.luvtrader.com','email_mode':EMAIL_MODE}}
        await db.settings.insert_one(s)
    return public(s)
DEFAULT_TEMPLATES={
 'monthly_estimate':{'subject':'Your LUVTrader monthly estimate','body':'Hi {{client_name}}, your {{subscription_type}} estimate is ${{estimate}}. Balance due is ${{balance}}. Pay via {{payment_info}}.'},
 'end_month_billing':{'subject':'Your LUVTrader board is clear','body':'Hi {{client_name}}, your sold total is ${{sold_total}}. Balance: ${{balance}}. Trips: {{trip_dates}}.'},
 'rt_bidding_reminder':{'subject':'RT bidding reminder','body':'Hi {{client_name}}, your RT month is next month. Please send board details by the 8th.'},
 'tap_retainer_offer':{'subject':'TAP retainer option','body':'Hi {{client_name}}, while on TAP, hold your spot for the TAP retainer at $75.'},
 'refund_credit_choice':{'subject':'Refund or credit choice','body':'Hi {{client_name}}, you have a ${{refund_credit}} credit/refund. Reply with refund or apply as credit.'}}
async def render_message(client_id, mtype, triggered_by):
    c=await db.clients.find_one({'id':client_id}); s=await settings(); tmpl=s['email_templates'][mtype]
    trips=[public(t) async for t in db.trips.find({'client_id':client_id})]
    vars={'client_name':c.get('cwa_name') or c.get('legal_name'),'subscription_type':c.get('subscription_type'),'estimate':c.get('monthly_estimate',0),'balance':c.get('balance',0),'sold_total':c.get('sold_total',0),'refund_credit':c.get('credit_refund_amount',0),'trip_dates':', '.join(t['trip_date'] for t in trips),'payment_info':' / '.join(s['payment_instructions'].values())}
    sub,body=tmpl['subject'],tmpl['body']
    for k,v in vars.items(): body=body.replace('{{'+k+'}}',str(v)); sub=sub.replace('{{'+k+'}}',str(v))
    instant=s['instant_send_toggles'].get(mtype,False); mode=s['global_business_settings'].get('email_mode',EMAIL_MODE)
    msg={'id':oid(),'client_id':client_id,'message_type':mtype,'subject':sub,'body':body,'status':'sent' if instant and mode=='send' else 'previewed','sent_date':now() if instant and mode=='send' else None,'created_date':now(),'triggered_by':triggered_by,'preview_before_send':not instant}
    await db.messages.insert_one(msg); return public(msg)
async def current(token=Depends(oauth2)):
    try: email=jwt.decode(token,JWT_SECRET,algorithms=[ALGO])['sub']
    except JWTError: raise HTTPException(401,'Invalid token')
    u=await db.users.find_one({'email':email});
    if not u: raise HTTPException(401,'User not found')
    return public(u)
def need(*roles):
    async def dep(u=Depends(current)):
        if u['role'] not in roles: raise HTTPException(403,'Insufficient role')
        return u
    return dep
async def recalc(client_id):
    sold=0
    async for t in db.trips.find({'client_id':client_id,'status':'sold'}): sold+=float(t.get('sale_amount',0))
    c=await db.clients.find_one({'id':client_id}); c['sold_total']=sold; c=calc(c); c['updated_date']=now(); await db.clients.replace_one({'id':client_id},c); return public(c)
@app.post('/api/auth/login')
async def login(form:OAuth2PasswordRequestForm=Depends()):
    u=await db.users.find_one({'email':form.username.lower()})
    if not u or not pwd.verify(form.password,u['password_hash']): raise HTTPException(400,'Incorrect email or password')
    return {'access_token':jwt.encode({'sub':u['email'],'exp':datetime.utcnow()+timedelta(days=7)},JWT_SECRET,algorithm=ALGO),'token_type':'bearer','user':public(u)}
@app.get('/api/me')
async def me(u=Depends(current)): return u
@app.get('/api/clients')
async def clients(active_only:bool=False,u=Depends(need('admin','operations'))):
    q={'client_status':{'$in':['active','single month','assisted']}} if active_only or u['role']=='operations' else {}
    return [calc(public(c)) async for c in db.clients.find(q).sort('cwa_name',1)]
@app.post('/api/clients')
async def add_client(c:ClientIn,u=Depends(need('admin'))):
    d=calc(c.model_dump()); d.update({'id':oid(),'sold_total':0,'created_date':now(),'updated_date':now()}); await db.clients.insert_one(d); return public(d)
@app.get('/api/clients/{cid}')
async def get_client(cid:str,u=Depends(current)):
    if u['role']=='client' and u.get('linked_client_id')!=cid: raise HTTPException(403,'Own client only')
    c=await db.clients.find_one({'id':cid});
    if not c: raise HTTPException(404,'Not found')
    return calc(public(c))
@app.put('/api/clients/{cid}')
async def upd_client(cid:str,c:ClientIn,u=Depends(need('admin','operations'))):
    old=await db.clients.find_one({'id':cid}); data=old|c.model_dump(); data=calc(data); data['updated_date']=now(); await db.clients.replace_one({'id':cid},data)
    if old.get('monthly_estimate')!=data.get('monthly_estimate'): await render_message(cid,'monthly_estimate',u['email'])
    if old.get('client_status')!=data.get('client_status') and data.get('client_status')=='TAP': await render_message(cid,'tap_retainer_offer',u['email'])
    return public(data)
@app.get('/api/trips')
async def trips(client_id:Optional[str]=None,u=Depends(current)):
    if u['role']=='client': client_id=u['linked_client_id']
    q={'client_id':client_id} if client_id else {}; return [public(t) async for t in db.trips.find(q).sort('trip_date',1)]
@app.post('/api/trips')
async def add_trip(t:TripIn,u=Depends(need('admin','operations'))):
    d=t.model_dump(); d.update({'id':oid(),'date_sold':None}); await db.trips.insert_one(d); await recalc(d['client_id']); return public(d)
@app.post('/api/trips/{tid}/sell')
async def sell(tid:str,payload:dict,u=Depends(need('admin','operations'))):
    t=await db.trips.find_one({'id':tid});
    if not t: raise HTTPException(404,'Trip not found')
    await db.trips.update_one({'id':tid},{'$set':{'status':'sold','sale_amount':float(payload.get('sale_amount',0)),'date_sold':now()}})
    c=await recalc(t['client_id']); log={'id':oid(),'client_id':t['client_id'],'trip_id':tid,'date_sold':now(),'amount_sold_for':float(payload.get('sale_amount',0)),'running_total_after_sale':c['sold_total']}; await db.sale_log.insert_one(log)
    remaining=await db.trips.count_documents({'client_id':t['client_id'],'status':'active'})
    if remaining==0: await render_message(t['client_id'],'end_month_billing',u['email'])
    if c['credit_refund_amount']>0: await render_message(t['client_id'],'refund_credit_choice',u['email'])
    return {'trip_id':tid,'client':c,'sale_log':public(log)}
@app.get('/api/sales')
async def sales(u=Depends(need('admin','operations'))): return [public(x) async for x in db.sale_log.find().sort('date_sold',-1)]
@app.get('/api/messages')
async def messages(client_id:Optional[str]=None,u=Depends(current)):
    if u['role']=='client': client_id=u['linked_client_id']
    q={'client_id':client_id} if client_id else {}; return [public(m) async for m in db.messages.find(q).sort('created_date',-1)]
@app.post('/api/messages/preview')
async def preview(m:MessageIn,u=Depends(need('admin'))):
    d=m.model_dump(); d.update({'id':oid(),'status':'previewed','sent_date':None,'created_date':now(),'triggered_by':u['email']}); await db.messages.insert_one(d); return public(d)
@app.post('/api/messages/{mid}/send')
async def send_msg(mid:str,payload:dict,u=Depends(need('admin'))):
    await db.messages.update_one({'id':mid},{'$set':{'subject':payload.get('subject'),'body':payload.get('body'),'status':'sent' if EMAIL_MODE=='send' else 'previewed','sent_date':now() if EMAIL_MODE=='send' else None}}); return public(await db.messages.find_one({'id':mid}))
@app.post('/api/messages/tap-offer')
async def tap_offer(u=Depends(need('admin'))):
    out=[]
    async for c in db.clients.find({'client_status':{'$in':['TAP','paused']}}): out.append(await render_message(c['id'],'tap_retainer_offer',u['email']))
    return out
@app.get('/api/settings')
async def get_settings(u=Depends(need('admin'))): return await settings()
@app.put('/api/settings')
async def put_settings(s:SettingsIn,u=Depends(need('admin'))):
    d=s.model_dump(); d['id']='global'; await db.settings.replace_one({'id':'global'},d,upsert=True); return d
@app.post('/api/seed')
async def seed():
    await db.users.delete_many({}); await db.clients.delete_many({}); await db.trips.delete_many({}); await db.sale_log.delete_many({}); await db.messages.delete_many({}); await db.settings.delete_many({})
    statuses=[('Maya Active','active','premium $250'),('Jordan Single','single month','single month $300'),('Casey TAP','TAP','premium $250'),('Riley Retainer','TAP retainer','TAP retainer $75'),('Taylor Paused','paused','assisted $75')]
    ids=[]
    for i,(name,st,sub) in enumerate(statuses,1):
        c=calc({'id':oid(),'employee_number':f'10{i}45','base':'DAL','cwa_name':name,'legal_name':name+' Legal','email':f'client{i}@example.com','phone':'555-0100','paypal':'billing@luvtrader.com','venmo':'@LUVTrader','zelle':'billing@luvtrader.com','payment_notes':'Confirm memo includes employee number.','posting_notes':'Post early AM; avoid overlap.','rotation_group':chr(64+i),'monthly_estimate':800+i*100,'amount_paid':300,'sold_total':0,'rt_month':'July','subscription_type':sub,'client_status':st,'internal_notes':'Demo account','admin_flags':['missing payment'] if i==2 else [],'created_date':now(),'updated_date':now()}); await db.clients.insert_one(c); ids.append(c['id'])
        for j in range(1,4):
            sold=j==1; amt=150+i*20 if sold else 0; await db.trips.insert_one({'id':oid(),'client_id':c['id'],'trip_date':f'2026-06-{10+i+j:02d}','trip_type':['reserve block','2-day','3-day'][j-1],'status':'sold' if sold else 'active','sale_amount':amt,'date_sold':now() if sold else None,'notes':'Demo trip'})
        await recalc(c['id'])
    users=[('Admin','admin@luvtrader.com','admin',None),('Ops','ops@luvtrader.com','operations',None),('Demo Client','client@example.com','client',ids[0])]
    for n,e,r,cid in users: await db.users.insert_one({'id':oid(),'name':n,'email':e,'password_hash':pwd.hash('password123'),'role':r,'linked_client_id':cid})
    await settings(); return {'seeded':True,'users':['admin@luvtrader.com','ops@luvtrader.com','client@example.com']}
@app.get('/api/health')
async def health(): return {'ok':True,'email_mode':EMAIL_MODE}
