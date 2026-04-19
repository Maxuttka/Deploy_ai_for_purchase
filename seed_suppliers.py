from pathlib import Path
import pandas as pd

from app.db.session import session_local, engine, Base
from app.db.models import Supplier


PATH = Path("suppliers_exploded.xlsx")


def norm(value) -> str:
    if pd.isna(value):
        return "-"
    value = str(value).strip()
    return value if value else "-"


def main():
    Base.metadata.create_all(bind=engine)
    df = pd.read_excel(PATH)
    db = session_local()
    try:
        db.query(Supplier).delete()
        db.commit()
        for _, row in df.iterrows():
            supplier = Supplier(
                brand=norm(row.get("Бренд")),
                category=norm(row.get("Категория товара ")),
                city=norm(row.get("Страна и город нахождения поставщика")),
                legal_entity=norm(row.get("Юр.лица поставщика (через запятую)")),
                shipping_method=norm(row.get("Через какие ТК отправляем")),
                website=norm(row.get("интернет-сайт (или ссылка на Alibaba)")),
                contact=norm(row.get("ФИО менеджеров с которыми мы работаем (через запятую)")),
                phone=norm(row.get("Номера телефонов (с добавычными если есть)(через запятую)")),
                email=norm(row.get("E-mail адреса (через запятую)")),
                status=norm(row.get("Статус (актив(закупается регулярно), пассив(не закупается, но есть на остатках), новинка(закупался один или несколько раз, не имеет истории продаж), вывод(не закупается и нет на остатках))")),
                buyer=norm(row.get("Кто занимается закупкой в ЛинуксЦентре")),
                work_conditions=norm(row.get("Какие условия и формат работы с поставщиком (предоплата, реализация, постоплата(срок постоплаты))")),
            )
            db.add(supplier)
        db.commit()
        count = db.query(Supplier).count()
        print(f"Загружено поставщиков: {count}")
    finally:
        db.close()

if __name__ == "__main__":
    main()