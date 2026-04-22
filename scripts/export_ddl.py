# -*- coding: utf-8 -*-
# 导出建表 SQL（DDL），用于在 MySQL 客户端中手动执行

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql

from backend.database import Base

if __name__ == "__main__":
    import backend.models  # noqa: F401

    output_path = Path(__file__).resolve().parent.parent / "scripts" / "schema_ddl.sql"
    dialect = mysql.dialect()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("-- 林小梦项目 MySQL 建表 DDL（由 SQLAlchemy 模型生成）\n\n")
        for table in Base.metadata.sorted_tables:
            ddl = str(CreateTable(table).compile(dialect=dialect))
            f.write(ddl + ";\n\n")
    print(f"DDL 已导出到: {output_path}")
