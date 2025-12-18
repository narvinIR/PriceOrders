import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# Конфигурация
API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="PriceOrders - Маппинг артикулов",
    page_icon="📦",
    layout="wide"
)

# Sidebar - навигация
st.sidebar.title("📦 PriceOrders")
page = st.sidebar.radio(
    "Навигация",
    ["🏠 Главная", "📋 Каталог", "👥 Клиенты", "📦 Заказы", "🔄 Новый заказ"]
)

def api_get(endpoint):
    try:
        r = requests.get(f"{API_URL}{endpoint}")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Ошибка API: {e}")
        return None

def api_post(endpoint, data=None, files=None):
    try:
        r = requests.post(f"{API_URL}{endpoint}", data=data, files=files)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Ошибка API: {e}")
        return None

# === Главная ===
if page == "🏠 Главная":
    st.title("PriceOrders - Система маппинга артикулов")
    st.markdown("""
    ### Возможности системы:
    - 📋 **Каталог товаров** - загрузка и управление вашим каталогом
    - 👥 **Клиенты** - база B2B клиентов
    - 📦 **Заказы** - обработка заказов с автоматическим маппингом
    - 📤 **Экспорт** - выгрузка в Excel для 1С

    ### Как это работает:
    1. Загрузите ваш каталог товаров
    2. Добавьте клиентов
    3. Загружайте заказы клиентов - система автоматически найдет соответствия
    4. Проверьте неопределённые позиции
    5. Экспортируйте готовый заказ для 1С
    """)

    # Статистика
    col1, col2, col3 = st.columns(3)

    products = api_get("/products/")
    clients = api_get("/clients/")
    orders = api_get("/orders/")

    with col1:
        st.metric("Товаров в каталоге", len(products) if products else 0)
    with col2:
        st.metric("Клиентов", len(clients) if clients else 0)
    with col3:
        st.metric("Заказов", len(orders) if orders else 0)

# === Каталог ===
elif page == "📋 Каталог":
    st.title("📋 Каталог товаров")

    tab1, tab2, tab3 = st.tabs(["Просмотр", "Цены со скидками", "Загрузка"])

    with tab1:
        products = api_get("/products/")
        if products:
            df = pd.DataFrame(products)
            if not df.empty:
                st.dataframe(
                    df[['sku', 'name', 'category', 'brand', 'unit', 'price', 'base_price']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Каталог пуст. Загрузите товары во вкладке 'Загрузка'")
        else:
            st.info("Каталог пуст")

    with tab2:
        st.subheader("💰 Таблица цен со скидками")
        DISCOUNTS = [50, 53, 55, 56, 57, 58, 59, 60]
        selected_discount = st.selectbox("Скидка клиента", DISCOUNTS, index=1)

        products = api_get(f"/products/with-prices/?discount={selected_discount}")
        if products:
            df = pd.DataFrame(products)
            if not df.empty and 'base_price' in df.columns:
                # Рассчитываем все скидки
                for d in DISCOUNTS:
                    df[f'{d}%'] = df['base_price'].apply(
                        lambda x: round(float(x) * (1 - d/100), 2) if x else None
                    )

                # Показываем таблицу
                cols = ['sku', 'name', 'category', 'base_price'] + [f'{d}%' for d in DISCOUNTS]
                st.dataframe(
                    df[cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "base_price": st.column_config.NumberColumn("База", format="%.2f"),
                        **{f'{d}%': st.column_config.NumberColumn(f'{d}%', format="%.2f") for d in DISCOUNTS}
                    }
                )

                # Экспорт в Excel
                if st.button("📥 Экспорт в Excel"):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df[cols].to_excel(writer, index=False, sheet_name='Цены')
                    st.download_button(
                        "⬇️ Скачать Excel",
                        data=output.getvalue(),
                        file_name="prices_with_discounts.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.info("Нет товаров с ценами")
        else:
            st.info("Загрузите каталог с ценами")

    with tab3:
        st.subheader("Загрузка каталога из Excel")
        uploaded_file = st.file_uploader(
            "Выберите файл Excel/CSV с каталогом",
            type=['xlsx', 'xls', 'csv']
        )

        if uploaded_file:
            st.info(f"Файл: {uploaded_file.name}")
            if st.button("📤 Загрузить каталог"):
                files = {'file': (uploaded_file.name, uploaded_file.getvalue())}
                result = api_post("/products/upload", files=files)
                if result:
                    st.success(f"Загружено товаров: {result.get('uploaded', 0)}")
                    st.rerun()

# === Клиенты ===
elif page == "👥 Клиенты":
    st.title("👥 Клиенты")

    tab1, tab2 = st.tabs(["Список", "Добавить"])

    with tab1:
        clients = api_get("/clients/")
        if clients:
            for client in clients:
                with st.expander(f"🏢 {client['name']}", expanded=False):
                    st.write(f"**ID:** `{client['id']}`")
                    if client.get('code'):
                        st.write(f"**Код:** {client['code']}")
                    if client.get('contact_email'):
                        st.write(f"**Email:** {client['contact_email']}")
                    if client.get('contact_phone'):
                        st.write(f"**Телефон:** {client['contact_phone']}")
        else:
            st.info("Нет клиентов")

    with tab2:
        st.subheader("Добавить клиента")
        with st.form("add_client"):
            name = st.text_input("Название*", placeholder="ООО Рога и Копыта")
            code = st.text_input("Код клиента", placeholder="RIK-001")
            email = st.text_input("Email", placeholder="orders@rik.ru")
            phone = st.text_input("Телефон", placeholder="+7 999 123-45-67")

            if st.form_submit_button("➕ Добавить"):
                if name:
                    data = {
                        "name": name,
                        "code": code or None,
                        "contact_email": email or None,
                        "contact_phone": phone or None,
                        "settings": {}
                    }
                    result = api_post("/clients/", data=None, files=None)
                    # Используем JSON
                    try:
                        r = requests.post(f"{API_URL}/clients/", json=data)
                        r.raise_for_status()
                        st.success(f"Клиент '{name}' добавлен!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ошибка: {e}")
                else:
                    st.warning("Введите название клиента")

# === Заказы ===
elif page == "📦 Заказы":
    st.title("📦 Заказы")

    # Фильтры
    col1, col2 = st.columns(2)
    with col1:
        clients = api_get("/clients/")
        client_options = {c['name']: c['id'] for c in (clients or [])}
        client_options = {"Все клиенты": None, **client_options}
        selected_client_name = st.selectbox("Клиент", list(client_options.keys()))
        selected_client = client_options[selected_client_name]

    with col2:
        status_filter = st.selectbox(
            "Статус",
            ["Все", "processing", "needs_review", "processed", "confirmed", "exported"]
        )

    # Запрос заказов
    params = []
    if selected_client:
        params.append(f"client_id={selected_client}")
    if status_filter != "Все":
        params.append(f"status={status_filter}")

    query = "?" + "&".join(params) if params else ""
    orders = api_get(f"/orders/{query}")

    if orders:
        for order in orders:
            client_name = order.get('clients', {}).get('name', order.get('client', {}).get('name', 'Unknown'))
            status_emoji = {
                'processing': '🔄',
                'needs_review': '⚠️',
                'processed': '✅',
                'confirmed': '✔️',
                'exported': '📤'
            }.get(order['status'], '❓')

            with st.expander(
                f"{status_emoji} Заказ #{order.get('order_number', order['id'][:8])} - {client_name}",
                expanded=False
            ):
                st.write(f"**ID:** `{order['id']}`")
                st.write(f"**Статус:** {order['status']}")
                st.write(f"**Создан:** {order['created_at']}")

                items = order.get('order_items', order.get('items', []))
                if items:
                    st.write(f"**Позиций:** {len(items)}")

                    items_df = []
                    for item in items:
                        product = item.get('products') or item.get('product') or {}
                        items_df.append({
                            'Арт. клиента': item['client_sku'],
                            'Название клиента': item.get('client_name', ''),
                            'Кол-во': item['quantity'],
                            'Арт. поставщика': product.get('sku', ''),
                            'Название поставщика': product.get('name', ''),
                            'Совпадение %': item.get('mapping_confidence', 0),
                            'Проверить': '⚠️' if item.get('needs_review') else '✅'
                        })

                    st.dataframe(pd.DataFrame(items_df), use_container_width=True, hide_index=True)

                # Действия
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📤 Экспорт Excel", key=f"export_{order['id']}"):
                        try:
                            r = requests.post(f"{API_URL}/orders/{order['id']}/export")
                            r.raise_for_status()
                            st.download_button(
                                "⬇️ Скачать файл",
                                data=r.content,
                                file_name=f"order_{order['id'][:8]}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"download_{order['id']}"
                            )
                        except Exception as e:
                            st.error(f"Ошибка экспорта: {e}")

                with col2:
                    if order['status'] in ['needs_review', 'processed']:
                        if st.button("✔️ Подтвердить", key=f"confirm_{order['id']}"):
                            try:
                                r = requests.post(f"{API_URL}/orders/{order['id']}/confirm")
                                r.raise_for_status()
                                st.success("Заказ подтверждён!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Ошибка: {e}")
    else:
        st.info("Нет заказов")

# === Новый заказ ===
elif page == "🔄 Новый заказ":
    st.title("🔄 Загрузка нового заказа")

    clients = api_get("/clients/")
    if not clients:
        st.warning("Сначала добавьте клиента в разделе 'Клиенты'")
    else:
        client_options = {c['name']: c['id'] for c in clients}

        with st.form("upload_order"):
            selected_client_name = st.selectbox("Клиент*", list(client_options.keys()))
            order_number = st.text_input("Номер заказа", placeholder="Опционально")
            uploaded_file = st.file_uploader(
                "Файл заказа (Excel/CSV)*",
                type=['xlsx', 'xls', 'csv']
            )

            st.markdown("""
            **Формат файла:**
            - Колонка с артикулом (артикул, sku, код)
            - Колонка с названием (название, наименование)
            - Колонка с количеством (количество, qty) - опционально
            """)

            if st.form_submit_button("📤 Загрузить и обработать"):
                if uploaded_file:
                    client_id = client_options[selected_client_name]

                    files = {'file': (uploaded_file.name, uploaded_file.getvalue())}
                    data = {
                        'client_id': client_id,
                        'order_number': order_number or None
                    }

                    with st.spinner("Обработка заказа..."):
                        try:
                            r = requests.post(
                                f"{API_URL}/orders/upload",
                                data=data,
                                files=files
                            )
                            r.raise_for_status()
                            result = r.json()

                            st.success("✅ Заказ загружен!")

                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Всего позиций", result['total_items'])
                            with col2:
                                st.metric("Автомаппинг", result['auto_mapped'])
                            with col3:
                                st.metric("Требует проверки", result['needs_review'])

                            if result['needs_review'] > 0:
                                st.warning(f"⚠️ {result['needs_review']} позиций требуют ручной проверки")

                            st.info(f"ID заказа: `{result['order_id']}`")

                        except Exception as e:
                            st.error(f"Ошибка загрузки: {e}")
                else:
                    st.warning("Выберите файл заказа")
