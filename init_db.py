"""数据库初始化脚本"""
from sqlalchemy import create_engine, text
import bcrypt

DB_URL = "mysql+pymysql://root:fjbw#123.@192.168.1.99:3306/fjbw_yqs?charset=utf8mb4"
engine = create_engine(DB_URL)

def hash_pwd(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# 建表SQL
init_sql = """
CREATE TABLE IF NOT EXISTS branches (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    code VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    real_name VARCHAR(50) NOT NULL,
    role ENUM('admin', 'branch_manager', 'employee') NOT NULL,
    branch_id INT,
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);

CREATE TABLE IF NOT EXISTS leads (
    id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(200) NOT NULL,
    credit_code VARCHAR(50),
    legal_person VARCHAR(50),
    reg_capital DECIMAL(15,2),
    establish_date VARCHAR(20),
    industry VARCHAR(100),
    business_scope TEXT,
    contact_name VARCHAR(50),
    contact_phone VARCHAR(20),
    revenue DECIMAL(15,2),
    employee_count INT,
    tax_type VARCHAR(50),
    accounting_status VARCHAR(50),
    needs TEXT,
    recommended_product VARCHAR(200),
    estimated_price DECIMAL(10,2),
    ai_analysis TEXT,
    status ENUM('new', 'following', 'converted', 'lost') DEFAULT 'new',
    priority ENUM('high', 'medium', 'low') DEFAULT 'medium',
    owner_id INT NOT NULL,
    branch_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);

CREATE TABLE IF NOT EXISTS customers (
    id INT PRIMARY KEY AUTO_INCREMENT,
    company_name VARCHAR(200) NOT NULL,
    credit_code VARCHAR(50) UNIQUE,
    legal_person VARCHAR(50),
    industry VARCHAR(100),
    contact_name VARCHAR(50),
    contact_phone VARCHAR(20),
    revenue DECIMAL(15,2),
    employee_count INT,
    tax_type VARCHAR(50),
    product_name VARCHAR(200),
    contract_amount DECIMAL(15,2),
    contract_start DATE,
    contract_end DATE,
    status ENUM('active', 'inactive', 'expired') DEFAULT 'active',
    owner_id INT NOT NULL,
    branch_id INT NOT NULL,
    source_lead_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id),
    FOREIGN KEY (source_lead_id) REFERENCES leads(id)
);

CREATE TABLE IF NOT EXISTS follow_ups (
    id INT PRIMARY KEY AUTO_INCREMENT,
    lead_id INT,
    customer_id INT,
    follow_type ENUM('phone', 'visit', 'wechat', 'email', 'other') NOT NULL,
    follow_time TIMESTAMP NOT NULL,
    content TEXT NOT NULL,
    result VARCHAR(200),
    next_plan TEXT,
    customer_feedback TEXT,
    user_id INT NOT NULL,
    branch_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);

CREATE TABLE IF NOT EXISTS lead_stage_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    lead_id INT NOT NULL,
    from_stage VARCHAR(30),
    to_stage VARCHAR(30) NOT NULL,
    remark VARCHAR(500),
    user_id INT NOT NULL,
    branch_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lead_id) REFERENCES leads(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (branch_id) REFERENCES branches(id)
);
"""

with engine.connect() as conn:
    # 建表
    for stmt in init_sql.strip().split(';\n'):
        if stmt.strip():
            conn.execute(text(stmt))
    conn.commit()
    
    # 迁移：添加销售阶段字段
    try:
        conn.execute(text("""
            ALTER TABLE leads ADD COLUMN sales_stage VARCHAR(30) DEFAULT 'new_lead' COMMENT '销售阶段'
        """))
        conn.commit()
        print("✅ 销售阶段字段已添加")
    except Exception:
        pass  # 字段已存在则跳过
    
    try:
        conn.execute(text("""
            ALTER TABLE leads ADD COLUMN stage_updated_at TIMESTAMP NULL COMMENT '阶段更新时间'
        """))
        conn.commit()
        print("✅ 阶段更新字段已添加")
    except Exception:
        pass
    
    print("✅ 数据表创建成功")
    
    # 插入初始数据
    branches = [
        ("总部", "HQ"),
        ("福州分公司", "FZ"),
        ("厦门分公司", "XM")
    ]
    
    for name, code in branches:
        conn.execute(text("INSERT IGNORE INTO branches (name, code) VALUES (:name, :code)"), {"name": name, "code": code})
    conn.commit()
    print("✅ 分公司数据初始化完成")
    
    # 插入用户
    users = [
        ("admin", hash_pwd("admin123"), "管理员", "admin", None),
        ("manager1", hash_pwd("manager123"), "张经理", "branch_manager", 2),
        ("manager2", hash_pwd("manager123"), "李经理", "branch_manager", 3),
        ("emp1", hash_pwd("emp123"), "王小明", "employee", 2),
        ("emp2", hash_pwd("emp123"), "李小红", "employee", 2),
        ("emp3", hash_pwd("emp123"), "陈大强", "employee", 3),
    ]
    
    for username, pwd, real_name, role, branch_id in users:
        try:
            conn.execute(
                text("INSERT INTO users (username, password_hash, real_name, role, branch_id) VALUES (:u, :p, :r, :ro, :b)"),
                {"u": username, "p": pwd, "r": real_name, "ro": role, "b": branch_id}
            )
        except:
            pass  # 已存在则跳过
    conn.commit()
    print("✅ 用户数据初始化完成")
    print("\n📋 账号信息:")
    print("  管理员: admin / admin123")
    print("  福州经理: manager1 / manager123")
    print("  厦门经理: manager2 / manager123")
    print("  福州员工: emp1,emp2 / emp123")
    print("  厦门员工: emp3 / emp123")
