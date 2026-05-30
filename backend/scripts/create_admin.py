#!/usr/bin/env python3
"""
创建管理员用户脚本

用法:
    python scripts/create_admin.py
    python scripts/create_admin.py --username admin --email admin@example.com
"""

import os
import sys
import argparse

# 将项目根目录添加到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.user import User, UserRole, UserStatus
from app.core.security import get_password_hash


def create_admin_user(
    db: Session,
    username: str = "admin",
    email: str = "admin@example.com",
    password: str = "Admin123!",
    full_name: str = "Administrator"
) -> User:
    """创建管理员用户"""
    # 检查用户是否已存在
    existing_user = db.query(User).filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        print(f"用户已存在: {username} ({email})")
        return existing_user

    # 创建新用户
    user = User(
        username=username,
        email=email,
        password_hash=get_password_hash(password),
        full_name=full_name,
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        login_attempts=0
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    print(f"管理员用户创建成功!")
    print(f"  用户名: {username}")
    print(f"  邮箱: {email}")
    print(f"  密码: {password}")
    print(f"  角色: {user.role.value}")

    return user


def main():
    parser = argparse.ArgumentParser(
        description="创建 XR 测试平台管理员用户"
    )
    parser.add_argument(
        "--username", "-u",
        default="admin",
        help="用户名 (默认: admin)"
    )
    parser.add_argument(
        "--email", "-e",
        default="admin@example.com",
        help="邮箱 (默认: admin@example.com)"
    )
    parser.add_argument(
        "--password", "-p",
        default="Admin123!",
        help="密码 (默认: Admin123!)"
    )
    parser.add_argument(
        "--full-name", "-n",
        default="Administrator",
        help="全名 (默认: Administrator)"
    )

    args = parser.parse_args()

    # 创建数据库会话
    db = SessionLocal()
    try:
        create_admin_user(
            db,
            username=args.username,
            email=args.email,
            password=args.password,
            full_name=args.full_name
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
