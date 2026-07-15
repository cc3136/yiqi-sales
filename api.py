"""
百旺销冠 V1.0 - 后端 API（纯接口，不含前端）
运行方式：python api.py --reload
访问：http://localhost:8000
"""

from fastapi import FastAPI, HTTPException, Depends, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import create_engine, Column, Integer, String, Date, DateTime, Enum, Text, JSON, ForeignKey, DECIMAL, Index, or_, and_, func, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime, timedelta
import bcrypt
from jose import jwt
import os

# ===== 配置 =====
DB_HOST = os.getenv("DB_HOST", "192.168.1.99")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "fjbw#123.")
DB_NAME = os.getenv("DB_NAME", "fjbw_yqs")
SECRET_KEY = os.getenv("SECRET_KEY", "yiqi-sales-secret-key-2026")
ALGORITHM = "HS256"

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"

# ===== 数据库 =====
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ===== 工具函数 =====
def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ===== 销售阶段常量 =====
LEAD_STAGES = [
    {"key": "new_lead", "name": "新建线索", "order": 1, "description": "线索刚刚录入，等待初步评估"},
    {"key": "first_contact", "name": "首次接触", "order": 2, "description": "已与客户取得联系，了解基本信息"},
    {"key": "needs_analysis", "name": "需求分析", "order": 3, "description": "深入了解客户财税需求和痛点"},
    {"key": "solution_design", "name": "方案设计", "order": 4, "description": "根据需求设计财税服务方案"},
    {"key": "proposal", "name": "报价方案", "order": 5, "description": "提交正式报价和方案建议书"},
    {"key": "negotiation", "name": "商务谈判", "order": 6, "description": "价格协商和合同条款讨论"},
    {"key": "closing", "name": "促成成交", "order": 7, "description": "签约/付款，最后促单阶段"},
    {"key": "won", "name": "已成交", "order": 8, "description": "签约成功，转化为客户"},
    {"key": "lost", "name": "已流失", "order": 9, "description": "客户流失或放弃跟进"},
]
LEAD_STAGE_MAP = {s["key"]: s for s in LEAD_STAGES}

# ===== 数据模型 =====
class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    address = Column(String(255))
    status = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(50), nullable=False)
    role = Column(Enum('admin', 'branch_manager', 'employee'), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"))
    phone = Column(String(20))
    status = Column(Integer, default=1)
    last_login = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    branch = relationship("Branch")

class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True)
    company_name = Column(String(200), nullable=False)
    credit_code = Column(String(18))
    legal_person = Column(String(50))
    reg_capital = Column(DECIMAL(15, 2))
    establish_date = Column(Date)
    business_scope = Column(Text)
    industry = Column(String(100))
    contact_name = Column(String(50))
    contact_phone = Column(String(20))
    revenue = Column(DECIMAL(15, 2))
    employee_count = Column(Integer)
    tax_type = Column(String(50))
    accounting_status = Column(String(50))
    monthly_voucher_count = Column(String(50))  # 月均凭证单量
    invoicing_status = Column(String(50))  # 开票状态
    needs = Column(Text)
    recommended_product = Column(String(200))
    estimated_price = Column(DECIMAL(15, 2))
    ai_analysis = Column(Text)
    add_on_services = Column(JSON)  # 增值服务列表
    sign_period = Column(String(20))  # 签约周期
    history_accounting = Column(String(50))  # 历史账务情况
    one_time_business = Column(String(50))  # 一次性业务
    status = Column(Enum('new', 'following', 'converted', 'lost', 'invalid'), default='new')
    priority = Column(Enum('high', 'medium', 'low'), default='medium')
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    tyc_company_id = Column(String(50))
    tyc_data = Column(JSON)
    converted_customer_id = Column(Integer, ForeignKey("customers.id"))
    converted_at = Column(DateTime)
    sales_stage = Column(String(30), default="new_lead", comment="销售阶段")
    stage_updated_at = Column(DateTime, comment="阶段更新时间")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_id])
    branch = relationship("Branch")

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    company_name = Column(String(200), nullable=False)
    credit_code = Column(String(18), unique=True, nullable=False)
    legal_person = Column(String(50))
    reg_capital = Column(DECIMAL(15, 2))
    establish_date = Column(Date)
    business_scope = Column(Text)
    industry = Column(String(100))
    contact_name = Column(String(50))
    contact_phone = Column(String(20))
    address = Column(String(255))
    revenue = Column(DECIMAL(15, 2))
    employee_count = Column(Integer)
    tax_type = Column(String(50))
    product_name = Column(String(200))
    contract_amount = Column(DECIMAL(15, 2))
    contract_start = Column(Date)
    contract_end = Column(Date)
    status = Column(Enum('active', 'inactive', 'expired'), default='active')
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    source_lead_id = Column(Integer, ForeignKey("leads.id"))
    tyc_data = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    owner = relationship("User", foreign_keys=[owner_id])
    branch = relationship("Branch")

class FollowUp(Base):
    __tablename__ = "follow_ups"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"))
    follow_type = Column(Enum('phone', 'visit', 'wechat', 'email', 'other'), nullable=False)
    follow_time = Column(DateTime, nullable=False)
    content = Column(Text, nullable=False)
    result = Column(String(200))
    next_plan = Column(Text)
    next_follow_date = Column(Date)
    customer_feedback = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

class LeadStageLog(Base):
    """线索阶段变更日志"""
    __tablename__ = "lead_stage_logs"
    id = Column(Integer, primary_key=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    from_stage = Column(String(30))
    to_stage = Column(String(30), nullable=False)
    remark = Column(String(500))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])

# ===== Pydantic Schemas =====
class LoginRequest(BaseModel):
    username: str
    password: str

class LeadCreate(BaseModel):
    company_name: str
    credit_code: Optional[str] = None
    legal_person: Optional[str] = None
    reg_capital: Optional[float] = None
    establish_date: Optional[str] = None
    industry: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    business_scope: Optional[str] = None

class LeadUpdate(BaseModel):
    revenue: Optional[float] = None
    employee_count: Optional[int] = None
    tax_type: Optional[str] = None
    accounting_status: Optional[str] = None
    monthly_voucher_count: Optional[str] = None
    invoicing_status: Optional[str] = None
    needs: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    recommended_product: Optional[str] = None
    estimated_price: Optional[float] = None
    ai_analysis: Optional[str] = None
    add_on_services: Optional[List[str]] = None
    sign_period: Optional[str] = None
    history_accounting: Optional[str] = None
    one_time_business: Optional[str] = None
    sales_stage: Optional[str] = None

class FollowUpCreate(BaseModel):
    lead_id: Optional[int] = None
    customer_id: Optional[int] = None
    follow_type: str
    follow_time: str
    content: str
    result: Optional[str] = None
    next_plan: Optional[str] = None
    next_follow_date: Optional[str] = None
    customer_feedback: Optional[str] = None
    # 阶段推进
    advance_stage: Optional[str] = None

class StageUpdate(BaseModel):
    stage: str
    remark: Optional[str] = None

# ===== 核心函数 =====
def create_token(user_id: int, role: str) -> str:
    payload = {"sub": str(user_id), "role": role}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="登录已过期")

def data_filter(user: User):
    """根据角色返回数据过滤条件"""
    if user.role == "admin":
        return {}
    elif user.role == "branch_manager":
        return {"branch_id": user.branch_id}
    else:
        return {"owner_id": user.id}

def ai_recommend(industry, revenue, employee_count, tax_type, accounting_status, needs, monthly_voucher_count=None, invoicing_status=None, add_on_services=None):
    """AI产品推荐引擎 - 基于百旺产品智能报价关键参数清单"""
    import re

    products = []          # 推荐产品线
    price_items = []       # 价格明细 [{name, price_low, price_high, reason}]
    warnings = []          # 合规性警告
    reason_parts = []      # 分析依据

    revenue = float(revenue) if revenue else 0
    emp_count = int(employee_count) if employee_count else 0
    voucher_count = monthly_voucher_count or ""
    inv_status = invoicing_status or ""
    addons = add_on_services or []
    ind = (industry or "").strip()
    needs_lower = (needs or "").strip()

    # ===== 第零层：合规性校验（接户限制） =====
    is_restricted = False
    # 建筑/机动车行业不接代申报
    if ind and ("建筑" in ind or "机动车" in ind):
        warnings.append("⚠️ 建筑/机动车行业为重点监管行业，不可接代申报，建议接代记账")
        is_restricted = True

    # 一般纳税人仅接0申报
    if tax_type == "一般纳税人" and accounting_status != "零申报":
        if is_restricted:
            warnings.append("⚠️ 一般纳税人需确认是否为零申报方可接代申报")

    # 小规模纳税人季度超30万/年超120万需引导代记账
    if tax_type == "小规模纳税人" and revenue > 120:
        warnings.append("⚠️ 年营收超120万，建议引导代记账服务")

    # ===== 第一层：纳税人类型 → 产品线 =====
    tax_type = tax_type or "小规模纳税人"

    # ===== 第二层：代申报 + 代记账分档 =====
    is_zero = (accounting_status == "零申报") or (revenue <= 0)
    is_zero_no_invoice = is_zero and (inv_status in ["不开票", "零申报不开票", ""])

    # --- 定额户 ---
    if tax_type == "定额户":
        products.append("代申报-定额户")
        price_items.append({"name": "定额户代申报", "price_low": 600, "price_high": 1200, "reason": "定期定额申报"})
        reason_parts.append("定额户，适用定期定额申报")

    # --- 小规模纳税人 ---
    elif tax_type == "小规模纳税人":
        # 代申报判断
        if is_zero and not is_restricted:
            products.append("代申报-小规模零申报")
            price_items.append({"name": "小规模零申报代申报", "price_low": 600, "price_high": 1200, "reason": "小规模零申报"})
            reason_parts.append("小规模零申报，可接代申报")

        # 代记账分档
        if is_zero_no_invoice:
            # X记账一档
            tier = "X记账一档"
            p_low, p_high = 1200, 1600
            reason_parts.append("零申报不开票，月凭证<50笔 → 小规模一档")
        elif revenue <= 120:
            tier = "X记账二档"
            p_low, p_high = 1600, 2200
            reason_parts.append(f"年收入{revenue}万（0-120万区间） → 小规模二档")
        elif revenue <= 300:
            if voucher_count in ["<100笔", "50-100笔", ""]:
                tier = "X记账三档"
                p_low, p_high = 2200, 3400
                reason_parts.append(f"年收入{revenue}万（120-300万），月凭证{voucher_count or '<100笔'} → 小规模三档")
            else:
                tier = "X记账四档"
                p_low, p_high = 3400, 5000
                reason_parts.append(f"年收入{revenue}万（300-500万） → 小规模四档")
        elif revenue <= 500:
            tier = "X记账四档"
            p_low, p_high = 3400, 5000
            reason_parts.append(f"年收入{revenue}万（300-500万） → 小规模四档")
        else:
            tier = "X记账四档（需评估升级一般纳税人）"
            p_low, p_high = 5000, 8000
            reason_parts.append(f"年收入{revenue}万超500万，建议评估是否升级一般纳税人")
            warnings.append("⚠️ 年收入较高，建议评估升级一般纳税人")

        products.append(f"代记账-{tier}")
        price_items.append({"name": f"代记账-{tier}", "price_low": p_low, "price_high": p_high, "reason": tier})

    # --- 一般纳税人 ---
    elif tax_type == "一般纳税人":
        # 一般纳税人仅0申报可接代申报
        if is_zero and not is_restricted:
            products.append("代申报-一般纳税人零申报")
            price_items.append({"name": "一般纳税人零申报代申报", "price_low": 800, "price_high": 1500, "reason": "一般纳税人零申报"})
            reason_parts.append("一般纳税人零申报，可接代申报")

        # Y系列分档
        if is_zero_no_invoice:
            tier = "Y记账一档"
            p_low, p_high = 1800, 3400
            reason_parts.append("零申报不开票，月凭证<50笔 → 一般纳税人一档")
        elif revenue <= 300:
            tier = "Y记账二档"
            p_low, p_high = 3400, 4800
            reason_parts.append(f"年收入{revenue}万（0-300万），月凭证<100笔 → 一般纳税人二档")
        elif revenue <= 800:
            tier = "Y记账三档"
            p_low, p_high = 4800, 8000
            reason_parts.append(f"年收入{revenue}万（300-800万），月1-2本凭证 → 一般纳税人三档")
        elif revenue <= 1500:
            tier = "Y记账四档"
            p_low, p_high = 7800, 10000
            reason_parts.append(f"年收入{revenue}万（800-1500万），月2-3本凭证 → 一般纳税人四档")
        else:
            tier = "Y记账五档"
            p_low, p_high = 10000, 15000
            reason_parts.append(f"年收入{revenue}万（1500万以上），月3+本凭证 → 一般纳税人五档")

        products.append(f"代记账-{tier}")
        price_items.append({"name": f"代记账-{tier}", "price_low": p_low, "price_high": p_high, "reason": tier})

    # ===== 第三层：行业加价 =====
    industry_surcharges = {
        "农业": {"keywords": ["农业", "种植", "养殖", "合作社", "非盈利"], "add_low": 500, "add_high": 2000, "name": "农业/合作社/非盈利加价"},
        "建筑业": {"keywords": ["建筑", "施工", "建设", "工程"], "add_low": 2000, "add_high": 5000, "name": "建筑行业加价（跨区域涉税）"},
        "出口退税": {"keywords": ["出口", "进出口"], "base_price": 12000, "name": "出口退税企业"},
        "电商": {"keywords": ["电商", "电子商务", "网络零售"], "add_low": 200, "add_high": 1500, "name": "电商行业加价"},
        "进销存": {"keywords": ["医药", "商超", "零售连锁"], "add_low": 200, "add_high": 1500, "name": "进销存项目加价"},
        "制造业": {"keywords": ["制造", "加工", "生产", "工厂"], "add_low": 300, "add_high": 1500, "name": "制造业加价"},
    }

    industry_extra = 0
    matched_industries = []
    for ind_key, ind_info in industry_surcharges.items():
        if ind and any(kw in ind for kw in ind_info["keywords"]):
            if "base_price" in ind_info:
                # 出口退税固定价格
                price_items.append({"name": ind_info["name"], "price_low": ind_info["base_price"], "price_high": ind_info["base_price"], "reason": "出口退税企业常规报价12000元起"})
                reason_parts.append(f"{ind_info['name']}：{ind}，常规报价12000元起")
            else:
                add_amt = ind_info["add_low"]
                price_items.append({"name": ind_info["name"], "price_low": ind_info["add_low"], "price_high": ind_info["add_high"], "reason": f"{ind}行业特殊加价"})
                reason_parts.append(f"{ind_info['name']}：+{ind_info['add_low']}-{ind_info['add_high']}元/年")
                industry_extra += add_amt
                matched_industries.append(ind_info["name"])

    # ===== 第四层：增值服务叠加 =====
    add_on_price_map = {
        "医社保开户": {"price": 200, "unit": "次"},
        "公积金开户": {"price": 200, "unit": "次"},
        "五险一金申报": {"price_low": 200, "price_high": 300, "unit": "年"},
        "代开发票": {"price_low": 200, "price_high": 500, "unit": "年"},
        "额外报表编制": {"price_low": 200, "price_high": 500, "unit": "次"},
        "申请一般纳税人": {"price": 100, "unit": "次"},
        "跨区域涉税-省内": {"price": 300, "unit": "次"},
        "跨区域涉税-跨省": {"price": 500, "unit": "次"},
        "上门服务-季度": {"price": 200, "unit": "4次/年"},
        "上门服务-全年": {"price": 500, "unit": "12次/年"},
        "打印装订凭证": {"price": 100, "unit": "次"},
    }

    add_on_total = 0
    add_on_details = []
    for addon in addons:
        if addon in add_on_price_map:
            info = add_on_price_map[addon]
            if "price" in info:
                p = info["price"]
                add_on_total += p
                add_on_details.append(f"{addon}：+{p}元/{info['unit']}")
            else:
                p_low = info.get("price_low", 0)
                add_on_total += p_low
                add_on_details.append(f"{addon}：+{info['price_low']}-{info['price_high']}元/{info['unit']}")
            price_items.append({"name": f"增值-{addon}", "price_low": info.get("price", info.get("price_low", 0)), "price_high": info.get("price", info.get("price_high", 0)), "reason": f"{addon}"})
            reason_parts.append(f"增值服务：{addon}")

    # ===== 汇总报价 =====
    total_low = sum(item["price_low"] for item in price_items)
    total_high = sum(item["price_high"] for item in price_items)

    # 一次性业务判断
    one_time_services = []
    if needs_lower:
        if "注册" in needs_lower or "工商" in needs_lower:
            one_time_services.append("工商注册（个体/公司）")
        if "变更" in needs_lower:
            one_time_services.append("工商变更")
        if "注销" in needs_lower:
            one_time_services.append("公司注销")
        if "资质" in needs_lower or "许可" in needs_lower:
            one_time_services.append("资质许可办理")

    return {
        "recommended_products": products,
        "estimated_price": total_low,
        "estimated_price_high": total_high,
        "price_items": price_items,
        "reason": "；".join(reason_parts),
        "additional_services": add_on_details,
        "add_on_total": add_on_total,
        "industry_extra": industry_extra,
        "warnings": warnings,
        "one_time_services": one_time_services,
        "tier_info": products[-1] if products else "",
        "quote_summary": f"基础服务费 ¥{total_low}-{total_high}/年" + (f"（含行业加价 ¥{industry_extra}）" if industry_extra > 0 else "") + (f" + 增值服务 ¥{add_on_total}/年" if add_on_total > 0 else "")
    }

# ===== FastAPI 应用 =====
app = FastAPI(title="亿企销冠 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 挂载前端静态文件
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend-vue", "dist")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ===== 健康检查 =====
@app.get("/api/health")
def health_check():
    """服务健康检查"""
    import pymysql
    db_status = "unknown"
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME, connect_timeout=3)
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"disconnected: {str(e)}"
    return {
        "status": "running",
        "database": db_status,
        "version": "1.0"
    }

# ===== 全局异常处理 =====
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理异常，返回结构化JSON"""
    error_msg = str(exc)
    if "Can't connect to MySQL" in error_msg or "timed out" in error_msg:
        return JSONResponse(
            status_code=503,
            content={"error": "数据库连接失败，请检查网络或数据库服务是否正常"}
        )
    return JSONResponse(
        status_code=500,
        content={"error": f"服务器内部错误: {error_msg[:200]}"}
    )

# ===== 数据库依赖（带错误处理） =====
def get_db_safe():
    """带错误处理的数据库会话"""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db.close()
        error_msg = str(e)
        if "Can't connect" in error_msg or "timed out" in error_msg:
            raise HTTPException(status_code=503, detail="数据库连接失败，请稍后重试")
        raise HTTPException(status_code=503, detail=f"数据库服务异常: {error_msg[:100]}")
    return db

# ===== 认证接口 =====
@app.post("/api/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user.last_login = datetime.now()
    db.commit()
    token = create_token(user.id, user.role)
    return {
        "access_token": token,
        "user": {
            "id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "role": user.role,
            "branch_id": user.branch_id,
            "branch_name": user.branch.name if user.branch else None
        }
    }

@app.get("/api/auth/me")
def get_me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "username": user.username,
        "real_name": user.real_name,
        "role": user.role,
        "branch_id": user.branch_id,
        "branch_name": user.branch.name if user.branch else None
    }


# ===== 线索接口 =====
@app.get("/api/leads")
def list_leads(
    page: int = 1, page_size: int = 20,
    keyword: Optional[str] = None, status: Optional[str] = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    query = db.query(Lead)
    for k, v in data_filter(user).items():
        query = query.filter(getattr(Lead, k) == v)
    if keyword:
        query = query.filter(Lead.company_name.contains(keyword))
    if status:
        query = query.filter(Lead.status == status)
    total = query.count()
    items = query.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "data": [
        {"id": l.id, "company_name": l.company_name, "credit_code": l.credit_code,
         "industry": l.industry, "status": l.status, "priority": l.priority,
         "recommended_product": l.recommended_product,
         "estimated_price": float(l.estimated_price) if l.estimated_price else None,
         "owner_name": l.owner.real_name if l.owner else None,
         "sales_stage": l.sales_stage or "new_lead",
         "stage_name": LEAD_STAGE_MAP.get(l.sales_stage or "new_lead", {}).get("name", "新建线索"),
         "stage_order": LEAD_STAGE_MAP.get(l.sales_stage or "new_lead", {}).get("order", 1),
         "created_at": str(l.created_at)} for l in items
    ]}

@app.post("/api/leads")
def create_lead(data: LeadCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    branch_id = user.branch_id
    if not branch_id:
        first_branch = db.query(Branch).filter(Branch.status == 1).first()
        if first_branch:
            branch_id = first_branch.id
        else:
            raise HTTPException(status_code=400, detail="请先创建分公司")
    lead = Lead(
        company_name=data.company_name, credit_code=data.credit_code,
        legal_person=data.legal_person, reg_capital=data.reg_capital,
        establish_date=date.fromisoformat(data.establish_date) if data.establish_date else None,
        industry=data.industry, contact_name=data.contact_name,
        contact_phone=data.contact_phone, business_scope=data.business_scope,
        owner_id=user.id, branch_id=branch_id, status="new"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return {"id": lead.id, "message": "线索创建成功"}

@app.put("/api/leads/{lead_id}")
def update_lead(lead_id: int, data: LeadUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(lead, k, v)
    lead.updated_at = datetime.now()
    db.commit()
    return {"message": "更新成功"}

@app.get("/api/leads/{lead_id}")
def get_lead(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    return {
        "id": lead.id, "company_name": lead.company_name, "credit_code": lead.credit_code,
        "legal_person": lead.legal_person, "reg_capital": float(lead.reg_capital) if lead.reg_capital else None,
        "establish_date": str(lead.establish_date) if lead.establish_date else None,
        "industry": lead.industry, "contact_name": lead.contact_name, "contact_phone": lead.contact_phone,
        "revenue": float(lead.revenue) if lead.revenue else None, "employee_count": lead.employee_count,
        "tax_type": lead.tax_type, "accounting_status": lead.accounting_status, "needs": lead.needs,
        "monthly_voucher_count": lead.monthly_voucher_count, "invoicing_status": lead.invoicing_status,
        "add_on_services": lead.add_on_services,
        "sign_period": lead.sign_period, "history_accounting": lead.history_accounting,
        "one_time_business": lead.one_time_business,
        "recommended_product": lead.recommended_product,
        "estimated_price": float(lead.estimated_price) if lead.estimated_price else None,
        "ai_analysis": lead.ai_analysis, "status": lead.status, "priority": lead.priority,
        "tyc_data": lead.tyc_data, "business_scope": lead.business_scope,
        "sales_stage": lead.sales_stage or "new_lead",
        "stage_name": LEAD_STAGE_MAP.get(lead.sales_stage or "new_lead", {}).get("name", "新建线索"),
        "stage_order": LEAD_STAGE_MAP.get(lead.sales_stage or "new_lead", {}).get("order", 1)
    }


class TYCSearchRequest(BaseModel):
    keyword: str

@app.post("/api/tyc-search")
def tyc_search(data: TYCSearchRequest):
    """天眼查企业搜索（调用天眼查MCP真实接口）"""
    import requests as req
    
    tyc_mcp_url = "https://mcp.tianyancha.com/v1"
    tyc_headers = {
        "Authorization": "11ee1322-f6d4-4f49-8b16-7103390709e6",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    try:
        # 1. 初始化MCP会话
        init_resp = req.post(tyc_mcp_url, headers=tyc_headers, json={
            "jsonrpc": "2.0", "method": "initialize", "id": 1,
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "yiqi-sales", "version": "1.0"}
            }
        }, timeout=10)
        session_id = init_resp.headers.get("mcp-session-id", "")
        
        # 2. 搜索企业
        search_headers = {**tyc_headers, "mcp-session-id": session_id}
        search_resp = req.post(tyc_mcp_url, headers=search_headers, json={
            "jsonrpc": "2.0", "method": "tools/call", "id": 2,
            "params": {
                "name": "search_companies",
                "arguments": {"query": data.keyword, "page": 1, "page_size": 10}
            }
        }, timeout=15)
        
        search_data = search_resp.json()
        if "result" not in search_data or "content" not in search_data["result"]:
            return {"error": "天眼查接口返回异常"}
        
        # 3. 解析Markdown表格
        content = search_data["result"]["content"][0].get("text", "")
        lines = content.split('\n')
        
        # 查找表格数据行
        companies = []
        for line in lines:
            if '|' in line and '企业名称' not in line and '---' not in line and '候选企业' not in line:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]  # 移除空字符串
                
                # 表格格式：序号 | 企业名称 | 统一社会信用代码 | 登记状态 | 法定代表人 | 注册资本 | 成立日期 | 企业类型 | 成立日期 | 企业ID | 匹配类型
                if len(parts) >= 8 and parts[0].isdigit():
                    # 解析成立日期（去掉时间部分）
                    est_date = parts[6].split(' ')[0] if len(parts) > 6 and parts[6] else ""
                    
                    companies.append({
                        "index": parts[0],
                        "company_name": parts[1],
                        "credit_code": parts[2],
                        "status": parts[3],
                        "legal_person": parts[4],
                        "reg_capital_str": parts[5],  # 保留原始字符串如"500万人民币"
                        "establish_date": est_date,
                        "company_type": parts[7] if len(parts) > 7 else "",
                        "company_id": parts[9] if len(parts) > 9 else ""
                    })
        
        # 4. 获取第一条企业的详细信息
        if companies:
            first_company = companies[0]
            
            # 调用get_company_basic_profile获取详细信息
            profile_resp = req.post(tyc_mcp_url, headers=search_headers, json={
                "jsonrpc": "2.0", "method": "tools/call", "id": 3,
                "params": {
                    "name": "get_company_basic_profile",
                    "arguments": {"company_name": first_company["company_name"]}
                }
            }, timeout=15)
            
            profile_data = profile_resp.json()
            if "result" in profile_data and "content" in profile_data["result"]:
                profile_content = profile_data["result"]["content"][0].get("text", "")
                
                # 解析注册资本（提取数字）
                reg_capital = 0
                try:
                    cap_str = first_company["reg_capital_str"]
                    # 提取数字部分
                    import re
                    match = re.search(r'(\d+(?:\.\d+)?)', cap_str)
                    if match:
                        reg_capital = float(match.group(1))
                except:
                    pass
                
                # 从 profile_text 解析行业、经营范围、联系电话
                industry = ""
                business_scope = ""
                contact_phone = ""
                
                # 解析 Markdown 表格中的字段
                lines = profile_content.split('\n')
                for i, line in enumerate(lines):
                    # 查找表格行：| 字段 | 值 |
                    if '|' in line and '##' not in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 3:
                            field_name = parts[1].strip()
                            field_value = parts[2].strip()
                            
                            if field_name == '行业' and field_value and not industry:
                                industry = field_value
                            elif field_name == '经营范围' and field_value and not business_scope:
                                business_scope = field_value
                            elif field_name == '联系电话' and field_value and not contact_phone:
                                contact_phone = field_value
                
                # 返回结构化数据
                return {
                    "company_name": first_company["company_name"],
                    "credit_code": first_company["credit_code"],
                    "legal_person": first_company["legal_person"],
                    "reg_capital": reg_capital,
                    "industry": industry,
                    "establish_date": first_company["establish_date"],
                    "business_scope": business_scope,
                    "contact_phone": contact_phone,
                    "profile_text": profile_content,  # 完整的企业画像文本
                    "all_companies": companies  # 所有搜索结果
                }
        
        return {
            "error": "未找到企业信息",
            "raw_result": content
        }
        
    except Exception as e:
        return {"error": f"天眼查查询失败: {str(e)}"}

class TYCPersonRequest(BaseModel):
    company_name: str
    person_name: str

@app.post("/api/tyc-person")
def tyc_person_search(data: TYCPersonRequest):
    """查询法人/股东的关联企业信息"""
    import requests as req
    import re

    tyc_mcp_url = "https://mcp.tianyancha.com/v1"
    tyc_headers = {
        "Authorization": "11ee1322-f6d4-4f49-8b16-7103390709e6",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    try:
        # 1. 初始化 MCP 会话
        init_resp = req.post(tyc_mcp_url, headers=tyc_headers, json={
            "jsonrpc": "2.0", "method": "initialize", "id": 1,
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "yiqi-sales", "version": "1.0"}
            }
        }, timeout=10)
        session_id = init_resp.headers.get("mcp-session-id", "")

        # 2. 查询人员画像
        search_headers = {**tyc_headers, "mcp-session-id": session_id}
        person_resp = req.post(tyc_mcp_url, headers=search_headers, json={
            "jsonrpc": "2.0", "method": "tools/call", "id": 2,
            "params": {
                "name": "get_person_profile",
                "arguments": {"company_name": data.company_name, "person_name": data.person_name}
            }
        }, timeout=15)

        person_data = person_resp.json()
        if "result" not in person_data or "content" not in person_data["result"]:
            return {"error": "查询人员信息失败"}

        person_content = person_data["result"]["content"][0].get("text", "")

        # 3. 解析任职企业/法定代表人企业/持股企业
        related_companies = []
        current_section = None

        lines = person_content.split('\n')
        for line in lines:
            # 识别当前区域
            if '法定代表人企业' in line:
                current_section = 'legal_rep'
            elif '持股企业' in line:
                current_section = 'shareholder'
            elif '任职企业' in line:
                current_section = 'executive'
            elif '##' in line and '企业' in line:
                current_section = None

            # 解析表格数据行
            if '|' in line and '---' not in line and '#' not in line.split('|')[0]:
                parts = [p.strip() for p in line.split('|')]
                parts = [p for p in parts if p]

                if len(parts) >= 4 and parts[0].isdigit():
                    company_info = {
                        "name": parts[1],
                        "status": parts[2],
                        "legal_person": parts[3] if len(parts) > 3 else "",
                        "reg_capital": parts[4] if len(parts) > 4 else "",
                        "establish_date": parts[5] if len(parts) > 5 else "",
                        "role": current_section
                    }
                    related_companies.append(company_info)

        # 去重（按企业名称）
        seen = set()
        unique_companies = []
        for c in related_companies:
            if c["name"] not in seen:
                seen.add(c["name"])
                unique_companies.append(c)

        return {
            "person_name": data.person_name,
            "company_name": data.company_name,
            "related_companies": unique_companies,
            "total": len(unique_companies),
            "profile_text": person_content
        }

    except Exception as e:
        return {"error": f"查询人员信息失败: {str(e)}"}


@app.post("/api/leads/{lead_id}/ai-recommend")
def lead_ai_recommend(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    result = ai_recommend(
        lead.industry, 
        float(lead.revenue) if lead.revenue else None,
        lead.employee_count, 
        lead.tax_type, 
        lead.accounting_status, 
        lead.needs,
        monthly_voucher_count=lead.monthly_voucher_count,
        invoicing_status=lead.invoicing_status,
        add_on_services=lead.add_on_services
    )
    lead.recommended_product = "、".join(result["recommended_products"])
    lead.estimated_price = result["estimated_price"]
    lead.ai_analysis = result["reason"]
    lead.add_on_services = result["additional_services"]
    db.commit()
    return result


# ===== 客户接口 =====
@app.get("/api/customers")
def list_customers(
    page: int = 1, page_size: int = 20, keyword: Optional[str] = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    query = db.query(Customer)
    for k, v in data_filter(user).items():
        query = query.filter(getattr(Customer, k) == v)
    if keyword:
        query = query.filter(Customer.company_name.contains(keyword))
    total = query.count()
    items = query.order_by(Customer.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "data": [
        {"id": c.id, "company_name": c.company_name, "credit_code": c.credit_code,
         "industry": c.industry, "status": c.status,
         "product_name": c.product_name, "contract_amount": float(c.contract_amount) if c.contract_amount else None,
         "contract_end": str(c.contract_end) if c.contract_end else None,
         "owner_name": c.owner.real_name if c.owner else None} for c in items
    ]}

@app.get("/api/customers/expiring")
def get_expiring_customers(days: int = 30, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取即将到期的客户列表"""
    from datetime import timedelta
    today = date.today()
    end_date = today + timedelta(days=days)
    
    query = db.query(Customer).filter(
        Customer.contract_end != None,
        Customer.contract_end >= today,
        Customer.contract_end <= end_date,
        Customer.status == 'active'
    )
    
    # 按权限过滤
    for k, v in data_filter(user).items():
        query = query.filter(getattr(Customer, k) == v)
    
    items = query.order_by(Customer.contract_end.asc()).all()
    
    return {
        "total": len(items),
        "days": days,
        "data": [
            {
                "id": c.id,
                "company_name": c.company_name,
                "contact_name": c.contact_name,
                "contact_phone": c.contact_phone,
                "product_name": c.product_name,
                "contract_end": str(c.contract_end),
                "days_left": (c.contract_end - today).days,
                "owner_name": c.owner.real_name if c.owner else None
            }
            for c in items
        ]
    }

@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="客户不存在")
    return {
        "id": c.id, "company_name": c.company_name, "credit_code": c.credit_code,
        "legal_person": c.legal_person, "industry": c.industry,
        "contact_name": c.contact_name, "contact_phone": c.contact_phone,
        "revenue": float(c.revenue) if c.revenue else None, "employee_count": c.employee_count,
        "product_name": c.product_name, "contract_amount": float(c.contract_amount) if c.contract_amount else None,
        "contract_start": str(c.contract_start) if c.contract_start else None,
        "contract_end": str(c.contract_end) if c.contract_end else None,
        "status": c.status, "owner_name": c.owner.real_name if c.owner else None
    }

@app.post("/api/leads/{lead_id}/convert")
def convert_lead(lead_id: int, product_name: str, contract_amount: float,
                 contract_start: str, contract_end: str,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if lead.status == "converted":
        raise HTTPException(status_code=400, detail="已转化")

    customer = Customer(
        company_name=lead.company_name, credit_code=lead.credit_code or ("TEMP" + str(lead.id)),
        legal_person=lead.legal_person, reg_capital=lead.reg_capital,
        establish_date=lead.establish_date, industry=lead.industry,
        contact_name=lead.contact_name, contact_phone=lead.contact_phone,
        revenue=lead.revenue, employee_count=lead.employee_count, tax_type=lead.tax_type,
        product_name=product_name, contract_amount=contract_amount,
        contract_start=date.fromisoformat(contract_start),
        contract_end=date.fromisoformat(contract_end),
        status="active", owner_id=lead.owner_id, branch_id=lead.branch_id,
        source_lead_id=lead_id, tyc_data=lead.tyc_data
    )
    db.add(customer)
    db.flush()
    lead.status = "converted"
    lead.converted_customer_id = customer.id
    lead.converted_at = datetime.now()
    # 记录阶段推进到"已成交"
    _log_stage_change(db, lead, "won", f"转化为客户：{product_name} ¥{contract_amount}", user)
    db.commit()
    return {"customer_id": customer.id, "message": "转化成功"}


# ===== 跟进接口 =====
@app.post("/api/follow-ups")
def create_follow_up(data: FollowUpCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    branch_id = user.branch_id
    if not branch_id:
        first_branch = db.query(Branch).filter(Branch.status == 1).first()
        branch_id = first_branch.id if first_branch else None
    fu = FollowUp(
        lead_id=data.lead_id, customer_id=data.customer_id,
        follow_type=data.follow_type, follow_time=datetime.fromisoformat(data.follow_time),
        content=data.content, result=data.result,
        next_plan=data.next_plan,
        next_follow_date=date.fromisoformat(data.next_follow_date) if data.next_follow_date else None,
        customer_feedback=data.customer_feedback,
        user_id=user.id, branch_id=branch_id
    )
    db.add(fu)
    if data.lead_id:
        lead = db.query(Lead).filter(Lead.id == data.lead_id).first()
        if lead:
            lead.status = "following"
            lead.updated_at = datetime.now()
            # 如果提交了阶段推进，更新阶段并记录日志
            if data.advance_stage and data.advance_stage in LEAD_STAGE_MAP:
                _log_stage_change(db, lead, data.advance_stage, data.content[:100], user)
    db.commit()
    return {"id": fu.id, "message": "跟进记录创建成功"}

@app.get("/api/follow-ups/lead/{lead_id}")
def get_lead_follow_ups(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(FollowUp).filter(FollowUp.lead_id == lead_id).order_by(FollowUp.follow_time.desc()).all()
    return [{"id": f.id, "follow_type": f.follow_type, "follow_time": str(f.follow_time),
             "content": f.content, "result": f.result, "next_plan": f.next_plan,
             "user_name": f.user.real_name if f.user else None} for f in items]


# ===== 销售阶段管理 =====
def _log_stage_change(db, lead, to_stage, remark, user):
    """记录阶段变更日志"""
    from_stage = lead.sales_stage or "new_lead"
    if from_stage == to_stage:
        return
    log = LeadStageLog(
        lead_id=lead.id,
        from_stage=from_stage,
        to_stage=to_stage,
        remark=remark,
        user_id=user.id,
        branch_id=lead.branch_id or user.branch_id or 0
    )
    db.add(log)
    lead.sales_stage = to_stage
    lead.stage_updated_at = datetime.now()
    # stage 推进到 won/lost 时自动更新状态
    if to_stage == "won":
        lead.status = "converted"
    elif to_stage == "lost":
        lead.status = "lost"

@app.get("/api/leads/{lead_id}/stages")
def get_lead_stage_history(lead_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取线索的阶段变更历史"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    logs = db.query(LeadStageLog).filter(
        LeadStageLog.lead_id == lead_id
    ).order_by(LeadStageLog.created_at.desc()).all()
    history = [{
        "id": log.id,
        "from_stage": log.from_stage,
        "to_stage": log.to_stage,
        "from_stage_name": LEAD_STAGE_MAP.get(log.from_stage, {}).get("name", "") if log.from_stage else "",
        "to_stage_name": LEAD_STAGE_MAP.get(log.to_stage, {}).get("name", ""),
        "remark": log.remark,
        "user_name": log.user.real_name if log.user else None,
        "created_at": str(log.created_at)
    } for log in logs]
    return {
        "current_stage": lead.sales_stage or "new_lead",
        "current_stage_name": LEAD_STAGE_MAP.get(lead.sales_stage or "new_lead", {}).get("name", "新建线索"),
        "history": history,
        "stages": LEAD_STAGES  # 返回所有阶段定义
    }

@app.post("/api/leads/{lead_id}/advance-stage")
def advance_lead_stage(lead_id: int, data: StageUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """推进销售阶段"""
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    if data.stage not in LEAD_STAGE_MAP:
        raise HTTPException(status_code=400, detail=f"无效的阶段: {data.stage}")
    current_stage = lead.sales_stage or "new_lead"
    current_order = LEAD_STAGE_MAP.get(current_stage, {}).get("order", 0)
    new_order = LEAD_STAGE_MAP[data.stage]["order"]
    # 允许回退（如将 lost 改回 negotiation）和前进
    _log_stage_change(db, lead, data.stage, data.remark or "", user)
    lead.updated_at = datetime.now()
    db.commit()
    return {
        "message": f"阶段已推进到「{LEAD_STAGE_MAP[data.stage]['name']}」",
        "from_stage": current_stage,
        "to_stage": data.stage,
        "current_stage": data.stage,
        "current_stage_name": LEAD_STAGE_MAP[data.stage]["name"]
    }


# ===== 统计接口 =====
@app.get("/api/stats/overview")
def stats_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    df = data_filter(user)

    lq = db.query(Lead)
    for k, v in df.items():
        lq = lq.filter(getattr(Lead, k) == v)
    total_leads = lq.count()
    new_leads = lq.filter(Lead.status == 'new').count()
    converted_leads = lq.filter(Lead.status == 'converted').count()

    cq = db.query(Customer)
    for k, v in df.items():
        cq = cq.filter(getattr(Customer, k) == v)
    total_customers = cq.count()
    active_customers = cq.filter(Customer.status == 'active').count()
    total_amount = float(db.query(func.sum(Customer.contract_amount)).filter(
        Customer.status == 'active').scalar() or 0)

    return {
        "total_leads": total_leads,
        "new_leads": new_leads,
        "converted_leads": converted_leads,
        "conversion_rate": round(converted_leads / total_leads * 100, 1) if total_leads else 0,
        "total_customers": total_customers,
        "active_customers": active_customers,
        "total_amount": total_amount
    }

@app.get("/api/stats/branches")
def stats_branches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看")

    branches = db.query(Branch).all()
    result = []
    for b in branches:
        leads = db.query(Lead).filter(Lead.branch_id == b.id).count()
        customers = db.query(Customer).filter(Customer.branch_id == b.id).count()
        amount = float(db.query(func.sum(Customer.contract_amount)).filter(
            Customer.branch_id == b.id, Customer.status == 'active').scalar() or 0)
        employees = db.query(User).filter(User.branch_id == b.id, User.role == 'employee').count()
        result.append({
            "branch_id": b.id, "branch_name": b.name,
            "total_leads": leads, "total_customers": customers,
            "total_amount": amount, "active_employees": employees
        })
    return result

@app.get("/api/stats/employees")
def stats_employees(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ["admin", "branch_manager"]:
        raise HTTPException(status_code=403, detail="无权限")

    query = db.query(User).filter(User.role == 'employee')
    if user.role == "branch_manager":
        query = query.filter(User.branch_id == user.branch_id)

    employees = query.all()
    result = []
    for e in employees:
        leads = db.query(Lead).filter(Lead.owner_id == e.id).count()
        customers = db.query(Customer).filter(Customer.owner_id == e.id).count()
        amount = float(db.query(func.sum(Customer.contract_amount)).filter(
            Customer.owner_id == e.id, Customer.status == 'active').scalar() or 0)
        result.append({
            "user_id": e.id, "user_name": e.real_name,
            "branch_name": e.branch.name if e.branch else "",
            "total_leads": leads, "total_customers": customers, "total_amount": amount
        })
    return result


# ===== 分公司列表 =====
@app.get("/api/branches")
def list_branches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    branches = db.query(Branch).filter(Branch.status == 1).all()
    return [{"id": b.id, "name": b.name, "code": b.code} for b in branches]


# ===== 用户管理接口（仅admin可用） =====
class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str
    branch_id: Optional[int] = None
    phone: Optional[str] = None

class UserUpdate(BaseModel):
    real_name: Optional[str] = None
    role: Optional[str] = None
    branch_id: Optional[int] = None
    phone: Optional[str] = None
    status: Optional[int] = None

class BranchCreate(BaseModel):
    name: str
    code: str
    address: Optional[str] = None

@app.get("/api/users")
def list_users(
    branch_id: Optional[int] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """获取用户列表（仅admin可用）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    query = db.query(User)
    if branch_id:
        query = query.filter(User.branch_id == branch_id)
    if role:
        query = query.filter(User.role == role)
    
    users = query.all()
    return [{
        "id": u.id,
        "username": u.username,
        "real_name": u.real_name,
        "role": u.role,
        "branch_id": u.branch_id,
        "branch_name": u.branch.name if u.branch else None,
        "phone": u.phone,
        "status": u.status,
        "created_at": str(u.created_at)
    } for u in users]

@app.post("/api/users")
def create_user(data: UserCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """创建用户（仅admin可用）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    # 检查用户名是否已存在
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    password_hash = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    new_user = User(
        username=data.username,
        password_hash=password_hash,
        real_name=data.real_name,
        role=data.role,
        branch_id=data.branch_id,
        phone=data.phone,
        status=1
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {"id": new_user.id, "message": "用户创建成功"}

@app.put("/api/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """更新用户（仅admin可用）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(target_user, k, v)
    
    db.commit()
    return {"message": "用户更新成功"}

class ResetPasswordRequest(BaseModel):
    new_password: str

@app.post("/api/users/{user_id}/reset-password")
def reset_user_password(user_id: int, data: ResetPasswordRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """重置用户密码（仅admin可用）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    password_hash = bcrypt.hashpw(data.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    target_user.password_hash = password_hash
    db.commit()
    
    return {"message": "密码重置成功"}

@app.post("/api/branches")
def create_branch(data: BranchCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """创建分公司（仅admin可用）"""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")
    
    # 检查编码是否已存在
    existing = db.query(Branch).filter(Branch.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="分公司编码已存在")
    
    new_branch = Branch(
        name=data.name,
        code=data.code,
        address=data.address,
        status=1
    )
    db.add(new_branch)
    db.commit()
    db.refresh(new_branch)
    
    return {"id": new_branch.id, "message": "分公司创建成功"}


# ===== AI 销售教练 =====

# --- 话术模板库 ---
SALES_SCRIPTS = {
    "first_contact": {
        "制造业": [
            "您好，我是百旺的{sales_name}，专门服务制造业企业的财税合规。了解到贵公司在{industry}领域深耕多年，想跟您聊聊在进项抵扣和成本核算方面有没有需要优化的地方。",
            "很多制造业客户反馈，每到月底进项发票整理特别耗时，我们有套方案能帮财务人员节省60%的票据处理时间，方便花两分钟了解一下吗？",
            "{contact_name}总您好，我是百旺{sales_name}。我们最近在帮{city}不少制造企业做财税体检，发现很多企业在增值税税负率上还有优化空间。想给您做个免费诊断，您看什么时间方便？"
        ],
        "建筑业": [
            "您好，我是百旺的{sales_name}，专注为建筑企业提供财税服务。了解到建筑行业跨区域涉税比较多，我们在省内/跨省涉税申报方面有成熟方案，想跟您交流一下。",
            "{contact_name}总您好，很多建筑企业头疼的问题就是项目分散、票据归集难。我们有个客户之前每季度光整理发票就要花一周，用了我们的方案后缩短到了1天。方便了解一下吗？"
        ],
        "电商": [
            "您好，我是百旺的{sales_name}，专门帮电商企业处理多平台对账和税务合规问题。现在电商税务监管越来越严，想跟您聊聊怎么做合规筹划。",
            "{contact_name}总，现在很多电商客户关心的是多店铺、多平台的流水怎么合规入账。我们在这块有丰富经验，您看方便聊几分钟吗？"
        ],
        "default": [
            "您好，我是百旺的{sales_name}，我们是专业的企业财税服务商。了解到贵公司{company_name}在{industry}发展得很好，想跟您交流一下财税方面有没有可以优化的地方。",
            "{contact_name}总您好，我是百旺{sales_name}。我们最近在帮很多企业做免费的财税健康检查，发现不少企业在税务申报上存在一些可以改进的地方。想给您做个简单诊断，您看什么时间方便？",
            "您好，打扰了。我是百旺的{sales_name}，我们专注为{industry}企业提供代记账和税务服务。很多客户选择我们是因为我们能帮他们平均节省20%的财税成本，想给您也做个方案对比。"
        ]
    },
    "discovery": {
        "situation": [
            "目前公司大概有多少员工？财务团队有几个人？",
            "现在的记账方式是自己做还是外包？用的什么财务软件？",
            "公司目前月均大概有多少张发票？进项和销项比例大概是多少？",
            "公司目前是零申报还是正常经营？年营收大概在什么范围？"
        ],
        "problem": [
            "在税务申报上遇到过什么困难吗？比如有没有被预警过？",
            "目前记账过程中最头疼的问题是什么？是票据管理还是申报？",
            "有没有遇到过税务政策变化导致多缴税的情况？",
            "财务人员在报税季加班多吗？有没有出错的情况？"
        ],
        "implication": [
            "如果税务申报出了问题，对公司会有什么影响？您有没有遇到过类似的情况？",
            "财税不合规如果被发现，可能面临的罚款和滞纳金，您了解过吗？",
            "如果财务人员精力都花在基础记账上，是不是就没有时间做更有价值的财务分析了？",
            "进项抵扣不充分的话，每年可能多交的增值税其实是一笔不小的数目，您算过吗？"
        ],
        "need_payoff": [
            "如果能帮您每年节省15%-20%的财税成本，同时降低合规风险，您觉得价值有多大？",
            "如果财务人员可以从繁琐的记账中解放出来，专注于经营分析，这对公司意味着什么？",
            "如果有一个方案能让您随时掌握公司税务状况，再也不用担心被预警，这值多少钱？"
        ]
    },
    "presentation": {
        "制造业": [
            "基于您的情况，我推荐我们的{product}方案。这个方案专门针对制造业的特点，能帮您解决进项抵扣不充分、成本核算复杂的问题。我们服务的制造业客户平均降低了{saving_rate}%的财税成本。",
            "给您看个案例，{city}有家跟您规模差不多的制造企业，之前也是自己做账，每年多交了差不多{overpay_amount}万的冤枉税。用了我们的方案后，不仅合规了，还省了不少钱。"
        ],
        "default": [
            "根据我们刚才聊的情况，我推荐{product}方案。这个方案能帮您解决{pain_point}的问题，同时确保税务合规。我们服务的同行业客户普遍反馈效果很好。",
            "我帮您算了一笔账：用我们的方案，您每年可以节省约{saving_amount}的财税成本，同时把财务人员从繁琐的基础工作中解放出来。投入产出比是非常高的。",
            "我们的服务包含专业的{product}、及时的税务政策推送、以及一对一的财税顾问。相比您自己请一个会计，成本只有三分之一，但专业度更高。"
        ]
    },
    "objection_handling": {
        "价格太贵": [
            "理解您的顾虑。其实您算一下，目前请一个兼职会计每月也要{accountant_cost}，一年下来就是{annual_cost}。我们的方案一年才{our_price}，还包含税务筹划和合规保障，相当于用一半的钱享受更专业的服务。",
            "我理解预算方面的考虑。不过您可以这样想：如果不合规被查到，罚款可能就是我们服务费的{penalty_ratio}倍。而且我们有客户用了之后发现，光是进项抵扣优化这一项就值回了服务费。"
        ],
        "考虑一下": [
            "完全理解，这是重要的决定。方便问一下您主要想再考虑哪方面？是服务内容还是价格？我可以针对性地再帮您分析。",
            "当然可以，不过我担心拖久了可能会错过最佳的税务筹划时机。现在已经是{current_month}月了，如果这个季度开始服务，我们能帮您提前做好下半年的税务规划。"
        ],
        "自己有会计": [
            "有会计是好事，说明公司很重视财务管理。不过很多客户反馈，专业的事交给专业的团队做效果更好。我们的财税顾问可以和您的会计配合，会计专注内部核算，我们负责外部合规和筹划，效率更高。",
            "理解。很多有会计的企业选择我们，主要是因为我们可以提供更专业的税务筹划，帮企业合法省税。您的会计可以把精力放在经营管理上，两不耽误。"
        ],
        "不需要": [
            "理解。不过我想提醒您一下，今年税务监管力度加大了不少，特别是{tax_policy_change}。很多企业之前觉得没问题，结果被预警了才着急。做个免费的财税体检也不花您时间，至少心里有数。",
            "好的，打扰了。不过可以加个微信吗？我经常会分享一些最新的税务政策和避坑指南，对您肯定有帮助。"
        ],
        "default": [
            "理解您的顾虑。其实很多客户一开始也有同样的担心，但用了之后发现效果远超预期。要不我们先试用一个月，满意再长期合作？",
            "您的顾虑我完全理解。这样吧，我把我们客户的实际案例和数据整理一份发给您，您看完之后再决定也不迟。"
        ]
    },
    "closing": {
        "制造业": [
            "{contact_name}总，咱们今天聊的{product}方案，现在签约的话可以赶上这个月的账务处理。而且这个月我们有活动，首年可以享受{discount}折优惠，帮您一年省下来{save_amount}。合同我现在就可以帮您准备好，您看方便签字吗？",
        ],
        "default": [
            "{contact_name}总，根据咱们刚才聊的，{product}方案完全能解决您提到的{pain_point}问题。现在签约的话，我们下周就可以开始服务。早一天开始，早一天省心。合同我准备好了，您看是今天签还是明天？",
            "我看您对这个方案还是很认可的。现在正好有{promotion}的优惠活动，错过了就要恢复原价了。要不咱们今天就把合同定下来？我马上帮您安排服务团队。",
            "{contact_name}总，其实做这个决定很简单：一个月{monthly_cost}块钱，换来的是全年税务合规无忧，还有专业的财税顾问随时解答问题。您看咱们什么时候开始？"
        ]
    }
}

# 阶段中文名映射
STAGE_NAMES = {
    "first_contact": "首次接触",
    "discovery": "需求挖掘",
    "presentation": "方案呈现",
    "objection_handling": "异议处理",
    "closing": "促成成交"
}

# --- Pydantic 请求模型 ---
class OpportunitiesRequest(BaseModel):
    lead_id: Optional[int] = None
    scan_all: Optional[bool] = False

class ScanPersonRequest(BaseModel):
    lead_id: int

# --- 天眼查 MCP 调用辅助 ---
def _tyc_mcp_init():
    """初始化天眼查 MCP 会话，返回 (session_id, headers)"""
    import requests as req
    tyc_mcp_url = "https://mcp.tianyancha.com/v1"
    tyc_headers = {
        "Authorization": "11ee1322-f6d4-4f49-8b16-7103390709e6",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    init_resp = req.post(tyc_mcp_url, headers=tyc_headers, json={
        "jsonrpc": "2.0", "method": "initialize", "id": 1,
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "yiqi-sales", "version": "1.0"}
        }
    }, timeout=10)
    session_id = init_resp.headers.get("mcp-session-id", "")
    headers = {**tyc_headers, "mcp-session-id": session_id}
    return tyc_mcp_url, headers

def _tyc_call_tool(headers, tool_name, arguments, timeout=15):
    """调用天眼查 MCP 工具"""
    import requests as req
    tyc_mcp_url = "https://mcp.tianyancha.com/v1"
    resp = req.post(tyc_mcp_url, headers=headers, json={
        "jsonrpc": "2.0", "method": "tools/call", "id": 2,
        "params": {"name": tool_name, "arguments": arguments}
    }, timeout=timeout)
    data = resp.json()
    if "result" in data and "content" in data["result"]:
        return data["result"]["content"][0].get("text", "")
    return None

def _tyc_parse_person_companies(person_content):
    """解析人员画像中的关联企业列表"""
    related = []
    current_section = None
    for line in person_content.split('\n'):
        if '法定代表人企业' in line:
            current_section = 'legal_rep'
        elif '持股企业' in line:
            current_section = 'shareholder'
        elif '任职企业' in line:
            current_section = 'executive'
        elif '##' in line and '企业' in line:
            current_section = None
        if '|' in line and '---' not in line and '#' not in line.split('|')[0]:
            parts = [p.strip() for p in line.split('|')]
            parts = [p for p in parts if p]
            if len(parts) >= 4 and parts[0].isdigit():
                related.append({
                    "name": parts[1],
                    "status": parts[2],
                    "legal_person": parts[3] if len(parts) > 3 else "",
                    "reg_capital": parts[4] if len(parts) > 4 else "",
                    "establish_date": parts[5] if len(parts) > 5 else "",
                    "role": current_section
                })
    seen = set()
    unique = []
    for c in related:
        if c["name"] not in seen:
            seen.add(c["name"])
            unique.append(c)
    return unique

# --- 功能1：关联企业商机发现 ---
@app.post("/api/ai/opportunities")
def ai_opportunities(data: OpportunitiesRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """发现法人/股东的关联企业中不在系统内的新商机"""
    # 确定要扫描的线索列表
    if data.lead_id:
        leads = db.query(Lead).filter(Lead.id == data.lead_id).all()
    else:
        query = db.query(Lead).filter(Lead.status.in_(["new", "following"]))
        df = data_filter(user)
        for k, v in df.items():
            query = query.filter(getattr(Lead, k) == v)
        leads = query.order_by(Lead.created_at.desc()).limit(50).all()

    if not leads:
        return {"opportunities": [], "total": 0, "message": "没有可扫描的线索"}

    # 收集系统中已有的公司名称和统一社会信用代码
    existing_companies = set()
    existing_codes = set()
    for l in db.query(Lead.company_name, Lead.credit_code).all():
        existing_companies.add(l.company_name)
        if l.credit_code:
            existing_codes.add(l.credit_code)
    for c in db.query(Customer.company_name, Customer.credit_code).all():
        existing_companies.add(c.company_name)
        if c.credit_code:
            existing_codes.add(c.credit_code)

    opportunities = []

    for lead in leads:
        if not lead.legal_person:
            continue

        try:
            tyc_mcp_url, headers = _tyc_mcp_init()
            person_content = _tyc_call_tool(headers, "get_person_profile", {
                "company_name": lead.company_name,
                "person_name": lead.legal_person
            })
            if not person_content:
                continue

            related_companies = _tyc_parse_person_companies(person_content)

            for company in related_companies:
                # 跳过当前线索公司本身
                if company["name"] == lead.company_name:
                    continue
                # 判断是否已在系统中
                if company["name"] in existing_companies:
                    continue
                # 跳过非在营企业
                if company.get("status") and "在营" not in company["status"] and "存续" not in company["status"]:
                    continue

                role_label = {"legal_rep": "法定代表人", "shareholder": "持股", "executive": "任职"}
                opportunities.append({
                    "company_name": company["name"],
                    "company_status": company.get("status", ""),
                    "reg_capital": company.get("reg_capital", ""),
                    "establish_date": company.get("establish_date", ""),
                    "source_lead_id": lead.id,
                    "source_lead_name": lead.company_name,
                    "related_person": lead.legal_person,
                    "relation_type": role_label.get(company.get("role", ""), "关联"),
                    "relation_desc": f"{lead.legal_person}是{lead.company_name}的{role_label.get(company.get('role', ''), '关联方')}",
                    "reason": f"通过{lead.company_name}法人{lead.legal_person}的关联企业发现，该企业{company.get('status', '')}，注册资本{company.get('reg_capital', '未知')}"
                })
        except Exception:
            continue

    return {"opportunities": opportunities, "total": len(opportunities)}


# --- 功能2：智能跟进提醒 ---
@app.get("/api/ai/follow-up-reminders")
def ai_follow_up_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """智能分析跟进记录，生成四种提醒"""
    df = data_filter(user)
    today = datetime.now()
    seven_days_ago = today - timedelta(days=7)

    # 获取权限范围内的活跃线索
    lead_query = db.query(Lead).filter(Lead.status.in_(["new", "following"]))
    for k, v in df.items():
        lead_query = lead_query.filter(getattr(Lead, k) == v)
    leads = lead_query.all()

    need_follow_up = []       # 需要跟进
    suggest_change_contact = []  # 建议换人
    missing_info = []         # 信息不全
    underpriced = []          # 报价过低

    # 关键短语：表示联系不到决策人
    not_decision_keywords = ["不是负责人", "不是决策人", "不是老板", "不在", "打错了",
                             "不认识", "没这个人", "已经离职", "换了", "不负责这块",
                             "不是对接人", "找不到负责人", "联系不上"]

    for lead in leads:
        # ---- 1. 需要跟进：超过7天无跟进记录 ----
        latest_fu = db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id
        ).order_by(FollowUp.follow_time.desc()).first()

        if latest_fu is None:
            # 从未跟进过
            days_since = (today - lead.created_at).days if lead.created_at else 0
            need_follow_up.append({
                "lead_id": lead.id,
                "company_name": lead.company_name,
                "days_no_followup": days_since,
                "reason": f"线索创建{days_since}天，从未跟进",
                "priority": "high" if days_since > 14 else "medium"
            })
        elif latest_fu.follow_time < seven_days_ago:
            days_since = (today - latest_fu.follow_time).days
            need_follow_up.append({
                "lead_id": lead.id,
                "company_name": lead.company_name,
                "last_follow_time": str(latest_fu.follow_time),
                "days_no_followup": days_since,
                "reason": f"已{days_since}天未跟进，上次跟进时间{latest_fu.follow_time.strftime('%Y-%m-%d')}",
                "priority": "high" if days_since > 14 else "medium"
            })

        # ---- 2. 建议换人：跟进记录中多次出现联系不到决策人 ----
        follow_ups = db.query(FollowUp).filter(
            FollowUp.lead_id == lead.id
        ).all()
        not_found_count = 0
        for fu in follow_ups:
            content = (fu.content or "") + " " + (fu.result or "") + " " + (fu.customer_feedback or "")
            if any(kw in content for kw in not_decision_keywords):
                not_found_count += 1
        if not_found_count >= 2:
            suggest_change_contact.append({
                "lead_id": lead.id,
                "company_name": lead.company_name,
                "not_found_count": not_found_count,
                "total_followups": len(follow_ups),
                "reason": f"跟进{len(follow_ups)}次中有{not_found_count}次反馈联系不到决策人/负责人，建议通过天眼查查询其他联系方式",
                "suggestion": "可通过天眼查查询企业其他高管联系方式"
            })

        # ---- 3. 信息不全：关键字段缺失 ----
        missing_fields = []
        if not lead.revenue:
            missing_fields.append("营收")
        if not lead.employee_count:
            missing_fields.append("员工数")
        if not lead.tax_type:
            missing_fields.append("纳税人类型")
        if not lead.needs:
            missing_fields.append("需求描述")
        if not lead.accounting_status:
            missing_fields.append("记账状态")
        if not lead.contact_phone:
            missing_fields.append("联系电话")

        if len(missing_fields) >= 2:
            missing_info.append({
                "lead_id": lead.id,
                "company_name": lead.company_name,
                "missing_fields": missing_fields,
                "missing_count": len(missing_fields),
                "reason": f"缺少{len(missing_fields)}个关键字段：{'、'.join(missing_fields)}",
                "suggestion": f"下次跟进时重点了解：{'、'.join(missing_fields[:3])}"
            })

        # ---- 4. 报价过低：estimated_price 低于同规模/同行业平均 ----
        if lead.estimated_price and lead.estimated_price > 0:
            # 按纳税人类型和大致规模找相似线索/客户的平均报价
            similar = db.query(Lead).filter(
                Lead.id != lead.id,
                Lead.estimated_price > 0,
                Lead.tax_type == lead.tax_type
            )
            if lead.industry:
                similar = similar.filter(Lead.industry.contains(lead.industry[:2]))

            similar_prices = [float(s.estimated_price) for s in similar.all() if s.estimated_price]

            # 也对比客户表的合同金额
            similar_customers = db.query(Customer).filter(
                Customer.tax_type == lead.tax_type
            )
            if lead.industry:
                similar_customers = similar_customers.filter(Customer.industry.contains(lead.industry[:2]))
            similar_customer_prices = [float(c.contract_amount) for c in similar_customers.all() if c.contract_amount]

            all_prices = similar_prices + similar_customer_prices
            if len(all_prices) >= 2:
                avg_price = sum(all_prices) / len(all_prices)
                if float(lead.estimated_price) < avg_price * 0.7:
                    underpriced.append({
                        "lead_id": lead.id,
                        "company_name": lead.company_name,
                        "current_price": float(lead.estimated_price),
                        "avg_price": round(avg_price, 2),
                        "diff_percent": round((1 - float(lead.estimated_price) / avg_price) * 100, 1),
                        "sample_count": len(all_prices),
                        "reason": f"报价{float(lead.estimated_price)}元，低于同类型企业均价{round(avg_price)}元约{round((1 - float(lead.estimated_price) / avg_price) * 100)}%",
                        "suggestion": f"建议报价调整至{round(avg_price * 0.85)}-{round(avg_price)}元区间"
                    })

    # 按优先级排序
    need_follow_up.sort(key=lambda x: x["days_no_followup"], reverse=True)

    return {
        "need_follow_up": need_follow_up,
        "suggest_change_contact": suggest_change_contact,
        "missing_info": missing_info,
        "underpriced": underpriced,
        "summary": {
            "need_follow_up_count": len(need_follow_up),
            "suggest_change_contact_count": len(suggest_change_contact),
            "missing_info_count": len(missing_info),
            "underpriced_count": len(underpriced)
        }
    }


# --- 功能3：话术引导 ---
@app.get("/api/ai/sales-scripts")
def ai_sales_scripts(
    stage: str = Query("first_contact", description="销售阶段: first_contact/discovery/presentation/objection_handling/closing"),
    industry: Optional[str] = Query(None, description="客户行业"),
    product: Optional[str] = Query(None, description="产品类型"),
    company_name: Optional[str] = Query(None, description="客户公司名称"),
    contact_name: Optional[str] = Query(None, description="联系人姓名"),
    pain_point: Optional[str] = Query(None, description="客户痛点"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """根据销售阶段、行业、产品动态生成话术建议"""
    if stage not in SALES_SCRIPTS:
        raise HTTPException(status_code=400, detail=f"不支持的阶段: {stage}，可选: {', '.join(STAGE_NAMES.keys())}")

    stage_data = SALES_SCRIPTS[stage]
    variables = {
        "sales_name": user.real_name,
        "industry": industry or "贵行业",
        "product": product or "代记账服务",
        "company_name": company_name or "贵公司",
        "contact_name": contact_name or "您",
        "city": user.branch.name if user.branch else "本地",
        "pain_point": pain_point or "财税合规",
        # 占位变量（无实际数据时使用合理默认值）
        "saving_rate": "20",
        "overpay_amount": "3-5万",
        "saving_amount": "1-2万",
        "accountant_cost": "2000-3000元",
        "annual_cost": "2.4-3.6万",
        "our_price": str(float(product and "代记账" in product and 3000 or 5000)),
        "penalty_ratio": "3-5",
        "current_month": str(datetime.now().month),
        "tax_policy_change": "金税四期全面上线，对企业财税合规要求更高了",
        "discount": "9",
        "save_amount": "2000-5000元",
        "promotion": "新客户首年优惠",
        "monthly_cost": "几百"
    }

    scripts = []

    if stage == "discovery":
        # SPIN 提问法，四个维度全部返回
        for spin_key in ["situation", "problem", "implication", "need_payoff"]:
            spin_labels = {
                "situation": "背景问题（S）",
                "problem": "难点问题（P）",
                "implication": "暗示问题（I）",
                "need_payoff": "需求-回报问题（N）"
            }
            items = stage_data.get(spin_key, [])
            for text in items:
                try:
                    rendered = text.format(**variables)
                except (KeyError, IndexError):
                    rendered = text
                scripts.append({
                    "category": spin_labels[spin_key],
                    "script": rendered
                })
    elif stage == "objection_handling":
        # 异议处理：尝试匹配行业，同时返回常见异议
        objections_to_show = []
        if industry:
            for key in stage_data:
                if industry[:2] in key or key in (industry or ""):
                    objections_to_show.append(key)
        # 始终展示"价格太贵"和"考虑一下"
        for default_key in ["价格太贵", "考虑一下", "自己有会计", "不需要"]:
            if default_key not in objections_to_show:
                objections_to_show.append(default_key)

        for obj_key in objections_to_show:
            items = stage_data.get(obj_key, stage_data.get("default", []))
            for text in items:
                try:
                    rendered = text.format(**variables)
                except (KeyError, IndexError):
                    rendered = text
                scripts.append({
                    "category": f"应对「{obj_key}」",
                    "script": rendered
                })
    else:
        # first_contact / presentation / closing：优先行业匹配，否则 default
        items = None
        if industry:
            for key in stage_data:
                if key != "default" and (industry[:2] in key or key in (industry or "")):
                    items = stage_data[key]
                    break
        if items is None:
            items = stage_data.get("default", [])

        for text in items:
            try:
                rendered = text.format(**variables)
            except (KeyError, IndexError):
                rendered = text
            scripts.append({
                "category": STAGE_NAMES.get(stage, stage),
                "script": rendered
            })

    return {
        "stage": stage,
        "stage_name": STAGE_NAMES.get(stage, stage),
        "industry": industry,
        "product": product,
        "scripts": scripts,
        "total": len(scripts)
    }


# --- 功能3.2：场景话术分析（自由文本输入） ---
class ScenarioRequest(BaseModel):
    situation: str = Field(..., description="用户输入的销售场景描述")
    company_name: Optional[str] = Field(None, description="客户公司名称")
    contact_name: Optional[str] = Field(None, description="联系人姓名")

@app.post("/api/ai/sales-scripts/scenario")
def ai_sales_scripts_scenario(
    data: ScenarioRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """根据自由文本描述的场景，智能分析并匹配话术"""
    situation = data.situation.strip()
    if not situation:
        raise HTTPException(status_code=400, detail="请输入场景描述")

    # 关键词解析：从场景描述中提取关键信息
    analysis = {
        "industry": None,
        "product": None,
        "pain_point": None,
        "objection": None,
        "stage": None,
        "keywords": []
    }

    # 行业识别
    industry_keywords = {
        "制造业": ["制造", "工厂", "生产", "加工", "车间"],
        "建筑业": ["建筑", "工程", "施工", "工地", "项目"],
        "电商": ["电商", "淘宝", "京东", "拼多多", "网店", "店铺"],
        "餐饮": ["餐饮", "饭店", "餐厅", "酒楼", "美食"],
        "零售": ["零售", "超市", "商店", "门店", "连锁"],
        "服务": ["服务", "咨询", "代理", "中介"]
    }
    for ind, kws in industry_keywords.items():
        if any(kw in situation for kw in kws):
            analysis["industry"] = ind
            analysis["keywords"].append(ind)
            break

    # 产品识别
    product_keywords = {
        "代记账": ["代记账", "代理记账", "记账", "做账"],
        "税务筹划": ["税务筹划", "税筹", "节税", "税务优化"],
        "财税咨询": ["财税咨询", "财务咨询", "咨询"],
        "工商注册": ["工商注册", "注册公司", "营业执照"],
        "审计": ["审计", "验资", "审计报"]
    }
    for prod, kws in product_keywords.items():
        if any(kw in situation for kw in kws):
            analysis["product"] = prod
            analysis["keywords"].append(prod)
            break

    # 痛点识别
    pain_keywords = {
        "进项抵扣不足": ["进项", "抵扣", "发票不够"],
        "税务风险": ["税务风险", "被查", "罚款", "预警", "稽查"],
        "成本高": ["成本高", "费用高", "价格贵", "负担重"],
        "效率低": ["效率低", "耗时", "麻烦", "复杂"],
        "合规问题": ["合规", "不规范", "风险"]
    }
    for pain, kws in pain_keywords.items():
        if any(kw in situation for kw in kws):
            analysis["pain_point"] = pain
            analysis["keywords"].append(pain)
            break

    # 异议识别
    objection_keywords = {
        "价格太贵": ["贵", "价格高", "费用高", "太贵", "便宜点"],
        "考虑一下": ["考虑", "再想想", "再说", "不着急", "以后"],
        "自己有会计": ["有会计", "自己的会计", "内部会计", "专职会计"],
        "不需要": ["不需要", "不用", "没需求", "暂时不要"]
    }
    for obj, kws in objection_keywords.items():
        if any(kw in situation for kw in kws):
            analysis["objection"] = obj
            analysis["keywords"].append(obj)
            break

    # 销售阶段推断
    stage_hints = {
        "first_contact": ["第一次", "初次", "联系", "打电话", "拜访"],
        "discovery": ["了解", "需求", "情况", "现状", "问题"],
        "presentation": ["方案", "介绍", "展示", "演示", "推荐"],
        "objection_handling": ["但是", "可是", "异议", "担心", "顾虑", "太贵", "考虑"],
        "closing": ["签约", "成交", "合作", "付款", "合同"]
    }
    for stage, hints in stage_hints.items():
        if any(hint in situation for hint in hints):
            analysis["stage"] = stage
            break

    # 如果没有明确异议但有"但是/可是"，推断为异议处理阶段
    if not analysis["stage"] and ("但是" in situation or "可是" in situation or "不过" in situation):
        analysis["stage"] = "objection_handling"

    # 默认阶段
    if not analysis["stage"]:
        analysis["stage"] = "first_contact"

    # 生成场景分析总结
    analysis_text = "根据您描述的场景，AI分析如下：\n\n"

    if analysis["industry"]:
        analysis_text += f"• 识别到客户行业：{analysis['industry']}\n"
    if analysis["product"]:
        analysis_text += f"• 涉及产品/服务：{analysis['product']}\n"
    if analysis["pain_point"]:
        analysis_text += f"• 客户痛点：{analysis['pain_point']}\n"
    if analysis["objection"]:
        analysis_text += f"• 客户异议：{analysis['objection']}\n"
    analysis_text += f"• 建议销售阶段：{STAGE_NAMES.get(analysis['stage'], analysis['stage'])}\n"

    if analysis["objection"]:
        analysis_text += f"\n💡 建议策略：客户提出了「{analysis['objection']}」的异议，建议先认同客户感受，再通过价值对比和案例证明来化解顾虑。"
    elif analysis["pain_point"]:
        analysis_text += f"\n💡 建议策略：客户的核心痛点是「{analysis['pain_point']}」，建议重点强调我们的解决方案如何针对性地解决这个问题，并用具体数据说明效果。"

    # 匹配话术模板
    scripts = []
    stage = analysis["stage"]
    industry = analysis["industry"]
    product = analysis["product"] or "代记账服务"
    pain_point = analysis["pain_point"] or "财税合规"
    objection = analysis["objection"]

    variables = {
        "sales_name": user.real_name,
        "industry": industry or "贵行业",
        "product": product,
        "company_name": data.company_name or "贵公司",
        "contact_name": data.contact_name or "您",
        "city": user.branch.name if user.branch else "本地",
        "pain_point": pain_point,
        "saving_rate": "20",
        "overpay_amount": "3-5万",
        "saving_amount": "1-2万",
        "accountant_cost": "2000-3000元",
        "annual_cost": "2.4-3.6万",
        "our_price": "5000",
        "penalty_ratio": "3-5",
        "current_month": str(datetime.now().month),
        "tax_policy_change": "金税四期全面上线，对企业财税合规要求更高了",
        "discount": "9",
        "save_amount": "2000-5000元",
        "promotion": "新客户首年优惠",
        "monthly_cost": "几百"
    }

    # 如果有明确异议，优先返回异议处理话术
    if objection and objection in SALES_SCRIPTS.get("objection_handling", {}):
        stage_data = SALES_SCRIPTS["objection_handling"]
        items = stage_data.get(objection, [])
        for text in items:
            try:
                rendered = text.format(**variables)
            except (KeyError, IndexError):
                rendered = text
            scripts.append({
                "category": f"应对「{objection}」",
                "script": rendered,
                "tip": f"针对客户「{objection}」的异议，建议用价值对比和案例来化解"
            })
        # 额外追加当前推断阶段的通用话术
        stage_items = SALES_SCRIPTS.get(stage, {}).get("default", [])
        for text in stage_items:
            try:
                rendered = text.format(**variables)
            except (KeyError, IndexError):
                rendered = text
            scripts.append({
                "category": STAGE_NAMES.get(stage, stage) + "（通用）",
                "script": rendered,
                "tip": f"当前处于{STAGE_NAMES.get(stage, stage)}阶段，配合异议处理一起使用"
            })
    else:
        # 否则按阶段返回话术
        stage_data = SALES_SCRIPTS.get(stage, {})
        items = None

        # 优先匹配行业
        if industry:
            for key in stage_data:
                if key != "default" and (industry[:2] in key or key in industry):
                    items = stage_data[key]
                    break

        # 没有行业匹配则用默认
        if items is None or not items:
            items = stage_data.get("default", [])
            if not items:
                # 兜底：至少返回一些通用话术
                items = [
                    "{contact_name}总您好，我是百旺的{sales_name}，很高兴能跟您交流。我们专注为{industry}企业提供专业的财税服务，很多客户用了之后都说省心不少。方便花两分钟了解一下吗？",
                    "您好{contact_name}总，我是百旺{sales_name}。我们在{city}服务了很多像您这样的企业，口碑一直不错。最近有个针对{industry}企业的优惠方案，想给您介绍一下。"
                ]

        for text in items:
            try:
                rendered = text.format(**variables)
            except (KeyError, IndexError):
                # 如果模板变量替换失败，直接返回原文并清理占位符
                import re
                rendered = re.sub(r'\{[^}]+\}', '', text).strip()

            # 添加使用提示
            tip = ""
            if stage == "first_contact":
                tip = "首次接触重点是建立信任，不要急于推销"
            elif stage == "discovery":
                tip = "需求挖掘阶段多提问少说话，了解客户真实需求"
            elif stage == "presentation":
                tip = "方案呈现时要结合客户痛点，用数据说话"
            elif stage == "objection_handling":
                tip = "处理异议先认同再引导，避免直接反驳"
            elif stage == "closing":
                tip = "促成成交要敢于要求承诺，给出明确的下一步"

            scripts.append({
                "category": STAGE_NAMES.get(stage, stage),
                "script": rendered,
                "tip": tip
            })

    # 如果是需求挖掘阶段，额外返回SPIN提问话术
    stage_data_ref = SALES_SCRIPTS.get(stage, {})
    if stage == "discovery" and "situation" in stage_data_ref:
        spin_labels = {
            "situation": "背景问题（S）",
            "problem": "难点问题（P）",
            "implication": "暗示问题（I）",
            "need_payoff": "需求-回报问题（N）"
        }
        for spin_key in ["situation", "problem", "implication", "need_payoff"]:
            spin_items = stage_data_ref.get(spin_key, [])
            for text in spin_items[:2]:  # 每个维度只取前2条
                try:
                    rendered = text.format(**variables)
                except (KeyError, IndexError):
                    import re
                    rendered = re.sub(r'\{[^}]+\}', '', text).strip()
                scripts.append({
                    "category": spin_labels[spin_key],
                    "script": rendered,
                    "tip": "通过提问引导客户自己说出需求"
                })

    return {
        "analysis": analysis_text,
        "situation_summary": situation[:100] + ("..." if len(situation) > 100 else ""),
        "detected": {
            "industry": analysis["industry"],
            "product": analysis["product"],
            "pain_point": analysis["pain_point"],
            "objection": analysis["objection"],
            "stage": analysis["stage"],
            "stage_name": STAGE_NAMES.get(analysis["stage"], analysis["stage"])
        },
        "scripts": scripts,
        "total": len(scripts)
    }


# --- 功能4：企业知识库搜索（占位接口） ---
@app.get("/api/knowledge/search")
def knowledge_search(
    q: str = Query(..., description="搜索关键词"),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """企业知识库搜索（占位接口，待实现）"""
    return {
        "query": q,
        "results": [],
        "total": 0,
        "message": "企业知识库功能即将上线，支持产品手册、FAQ、成功案例等文档的智能检索"
    }


# ===== 前端路由：所有非 /api 请求都返回 index.html =====
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    file_path = os.path.join(FRONTEND_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="页面不存在")


# ===== 启动入口 =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
