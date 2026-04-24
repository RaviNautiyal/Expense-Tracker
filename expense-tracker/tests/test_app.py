import io
from pathlib import Path

from app import create_app


TEST_ROOT = Path(__file__).resolve().parent / ".testdata"
TEST_ROOT.mkdir(exist_ok=True)


def make_app(name):
    database_path = TEST_ROOT / f"{name}.db"
    if database_path.exists():
        database_path.unlink()

    return create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE_PATH": str(database_path),
            "DEMO_EMAIL": "demo@test.local",
            "DEMO_PASSWORD": "demo12345",
            "ADMIN_EMAIL": "admin@test.local",
            "ADMIN_PASSWORD": "admin12345",
        }
    )


def register(client, name="Test User", email="user@example.com", password="password123"):
    return client.post(
        "/register",
        data={"name": name, "email": email, "password": password},
        follow_redirects=True,
    )


def login(client, email="user@example.com", password="password123"):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def login_admin(client):
    app = client.application
    with app.app_context():
        from database.db import create_user, find_user_by_email
        from werkzeug.security import generate_password_hash

        if find_user_by_email("admin@test.local") is None:
            create_user("Admin User", "admin@test.local", generate_password_hash("admin12345"), role="admin")
    return login(client, email="admin@test.local", password="admin12345")


def test_register_creates_user_and_redirects_to_dashboard():
    app = make_app("register_flow")
    client = app.test_client()

    response = register(client)

    assert response.status_code == 200
    assert b"Your account has been created." in response.data
    assert b"Welcome, Test User" in response.data


def test_dashboard_requires_authentication():
    app = make_app("dashboard_auth")
    client = app.test_client()

    response = client.get("/dashboard", follow_redirects=True)

    assert response.status_code == 200
    assert b"Please sign in to continue." in response.data


def test_add_edit_and_delete_expense_flow():
    app = make_app("expense_crud")
    client = app.test_client()
    register(client)

    add_response = client.post(
        "/expenses/add",
        data={"amount": "99.50", "category": "Shopping", "date": "2026-04-24", "description": "Desk lamp"},
        follow_redirects=True,
    )
    assert b"Expense added successfully." in add_response.data

    with app.app_context():
        from database.db import get_filtered_expenses

        expense = get_filtered_expenses(1)[0]

    edit_response = client.post(
        f"/expenses/{expense['id']}/edit",
        data={"amount": "120.00", "category": "Shopping", "date": "2026-04-24", "description": "Desk lamp and bulb"},
        follow_redirects=True,
    )
    assert b"Expense updated successfully." in edit_response.data

    delete_response = client.post(f"/expenses/{expense['id']}/delete", follow_redirects=True)
    assert b"Expense deleted." in delete_response.data


def test_income_management_flow():
    app = make_app("income_crud")
    client = app.test_client()
    register(client)

    add_response = client.post(
        "/incomes/add",
        data={"amount": "2500.00", "source": "Salary", "date": "2026-04-01", "description": "April salary"},
        follow_redirects=True,
    )
    assert b"Income added successfully." in add_response.data
    assert b"April salary" in add_response.data

    with app.app_context():
        from database.db import get_filtered_incomes

        income = get_filtered_incomes(1)[0]

    edit_response = client.post(
        f"/incomes/{income['id']}/edit",
        data={"amount": "2600.00", "source": "Salary", "date": "2026-04-01", "description": "Updated salary"},
        follow_redirects=True,
    )
    assert b"Income updated successfully." in edit_response.data

    delete_response = client.post(f"/incomes/{income['id']}/delete", follow_redirects=True)
    assert b"Income deleted." in delete_response.data


def test_budget_alert_appears_on_dashboard():
    app = make_app("budget_alert")
    client = app.test_client()
    register(client)

    budget_response = client.post("/budgets", data={"category": "Food", "month": "2026-04", "amount": "100.00"}, follow_redirects=True)
    assert b"Food budget saved for Apr 2026." in budget_response.data

    client.post(
        "/expenses/add",
        data={"amount": "95.00", "category": "Food", "date": "2026-04-24", "description": "Groceries"},
        follow_redirects=True,
    )

    dashboard_response = client.get("/dashboard?budget_month=2026-04", follow_redirects=True)
    assert b"Budget alerts for Apr 2026" in dashboard_response.data
    assert b"95% used" in dashboard_response.data


def test_export_and_import_expenses():
    app = make_app("import_export")
    client = app.test_client()
    register(client)

    client.post(
        "/expenses/add",
        data={"amount": "80.00", "category": "Bills", "date": "2026-04-12", "description": "Internet"},
        follow_redirects=True,
    )

    preview_response = client.get("/expenses/export")
    assert b"CSV export ready" in preview_response.data
    assert b"2026-04-12,Bills,80.00,Internet" in preview_response.data

    csv_content = "\n".join(
        [
            "date,category,amount,description",
            "2026-04-10,Transport,18.50,Metro card",
            "2026-04-11,Food,42.00,Lunch meeting",
        ]
    )
    import_response = client.post(
        "/expenses/import",
        data={"budget_month": "2026-04", "csv_file": (io.BytesIO(csv_content.encode("utf-8")), "expenses.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Imported 2 expenses from CSV." in import_response.data


def test_reports_and_search_filters_render():
    app = make_app("reports_search")
    client = app.test_client()
    register(client)

    client.post("/expenses/add", data={"amount": "45.00", "category": "Food", "date": "2026-04-18", "description": "Lunch meeting"}, follow_redirects=True)
    client.post("/incomes/add", data={"amount": "3000.00", "source": "Salary", "date": "2026-04-01", "description": "April salary"}, follow_redirects=True)

    dashboard_response = client.get("/dashboard?search=Lunch&min_amount=40&max_amount=50", follow_redirects=True)
    assert b"Lunch meeting" in dashboard_response.data
    assert b"Net balance" in dashboard_response.data

    reports_response = client.get("/reports?year=2026", follow_redirects=True)
    assert b"2026 financial report" in reports_response.data
    assert b"Monthly report" in reports_response.data


def test_recurring_rule_generates_due_transactions():
    app = make_app("recurring_rules")
    client = app.test_client()
    register(client)

    response = client.post(
        "/recurring/add",
        data={
            "kind": "expense",
            "title": "Streaming Subscription",
            "amount": "19.99",
            "category": "Entertainment",
            "source": "",
            "cadence": "monthly",
            "start_date": "2026-03-01",
            "next_run_date": "2026-03-01",
            "end_date": "",
            "description": "Monthly streaming bill",
        },
        follow_redirects=True,
    )
    assert b"Recurring transaction saved." in response.data

    with app.app_context():
        from database.db import apply_due_recurring_transactions, get_filtered_expenses

        created = apply_due_recurring_transactions(1, today="2026-04-15")
        expenses = get_filtered_expenses(1, search="Monthly streaming bill")

    assert created >= 0
    assert len(expenses) >= 2


def test_dashboard_shows_advanced_analytics_and_recurring_page():
    app = make_app("advanced_dashboard")
    client = app.test_client()
    register(client)

    client.post(
        "/recurring/add",
        data={
            "kind": "income",
            "title": "Consulting Retainer",
            "amount": "900.00",
            "category": "",
            "source": "Consulting",
            "cadence": "monthly",
            "start_date": "2026-04-01",
            "next_run_date": "2026-05-01",
            "end_date": "",
            "description": "Monthly consulting retainer",
        },
        follow_redirects=True,
    )

    recurring_page = client.get("/recurring", follow_redirects=True)
    assert b"Recurring transactions" in recurring_page.data
    assert b"Consulting Retainer" in recurring_page.data

    dashboard_response = client.get("/dashboard?budget_month=2026-04", follow_redirects=True)
    assert b"Financial health" in dashboard_response.data
    assert b"Upcoming recurring activity" in dashboard_response.data
    assert b"Savings rate" in dashboard_response.data


def test_backup_restore_and_pdf_download():
    app = make_app("backup_restore")
    client = app.test_client()
    register(client)

    client.post(
        "/expenses/add",
        data={"amount": "61.00", "category": "Food", "date": "2026-04-20", "description": "Backup lunch"},
        follow_redirects=True,
    )
    client.post(
        "/incomes/add",
        data={"amount": "1200.00", "source": "Bonus", "date": "2026-04-20", "description": "Quarterly bonus"},
        follow_redirects=True,
    )

    backup_response = client.get("/data/backup")
    assert backup_response.status_code == 200
    assert backup_response.mimetype == "application/json"
    assert b"Backup lunch" in backup_response.data
    assert b"Quarterly bonus" in backup_response.data

    restore_payload = backup_response.data
    restore_response = client.post(
        "/data/restore",
        data={"backup_file": (io.BytesIO(restore_payload), "backup.json")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Backup restored successfully." in restore_response.data

    pdf_response = client.get("/reports/download/pdf?year=2026")
    assert pdf_response.status_code == 200
    assert pdf_response.mimetype == "application/pdf"
    assert pdf_response.data.startswith(b"%PDF")


def test_profile_update_and_password_change():
    app = make_app("profile_flow")
    client = app.test_client()
    register(client)

    profile_response = client.post(
        "/profile",
        data={"action": "profile", "name": "Updated User", "email": "updated@example.com"},
        follow_redirects=True,
    )
    assert b"Profile updated successfully." in profile_response.data

    password_response = client.post(
        "/profile",
        data={"action": "password", "current_password": "password123", "new_password": "newpass123", "confirm_password": "newpass123"},
        follow_redirects=True,
    )
    assert b"Password updated successfully." in password_response.data

    client.get("/logout")
    login_response = client.post("/login", data={"email": "updated@example.com", "password": "newpass123"}, follow_redirects=True)
    assert b"Welcome back" in login_response.data


def test_admin_can_manage_users_and_categories():
    app = make_app("admin_flow")
    client = app.test_client()

    response = login_admin(client)
    assert b"Welcome back" in response.data

    admin_page = client.get("/admin", follow_redirects=True)
    assert b"System management" in admin_page.data

    create_category_response = client.post("/admin/categories/create", data={"name": "Utilities"}, follow_redirects=True)
    assert b"Category created." in create_category_response.data

    client.get("/logout")
    register(client, name="Second User", email="second@example.com", password="password123")
    client.get("/logout")
    login_admin(client)

    with app.app_context():
        from database.db import find_user_by_email, get_all_categories

        second_user = find_user_by_email("second@example.com")
        utilities = next(category for category in get_all_categories() if category["name"] == "Utilities")

    role_response = client.post(f"/admin/users/{second_user['id']}/role", data={"role": "admin"}, follow_redirects=True)
    assert b"User role updated." in role_response.data

    update_category_response = client.post(
        f"/admin/categories/{utilities['id']}/update",
        data={"name": "Home Utilities", "is_active": "1"},
        follow_redirects=True,
    )
    assert b"Category updated." in update_category_response.data
