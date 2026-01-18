"""
TrendRadar Web 模块
提供 Web 界面和 API 服务
"""

import argparse
import uvicorn


def main():
    """Web 服务启动入口"""
    parser = argparse.ArgumentParser(description='TrendRadar Web 服务')
    parser.add_argument('--host', default='0.0.0.0', help='绑定地址 (默认: 0.0.0.0)')
    parser.add_argument('--port', '-p', type=int, default=8088, help='端口号 (默认: 8088)')
    parser.add_argument('--reload', action='store_true', help='开发模式，自动重载')
    parser.add_argument('--db', default='data/trendradar.db', help='数据库路径')
    
    args = parser.parse_args()
    
    # 设置数据库路径环境变量
    import os
    os.environ['TRENDRADAR_DB_PATH'] = args.db
    
    print(f"🚀 TrendRadar Web 服务启动中...")
    print(f"   地址: http://{args.host}:{args.port}")
    print(f"   数据库: {args.db}")
    
    uvicorn.run(
        "trendradar.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()
