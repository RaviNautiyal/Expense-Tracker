import csv
import io
import json
import sqlite3
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    Response,
    current_app,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash, generate_password_hash

from config import Config
from database.db import (
    apply_due_recurring_transactions,
    build_user_backup_payload,
    create_recurring_transaction,
    create_category,
    create_expense,
    create_expense_batch,
    create_income,
    create_user,
    delete_category,
    delete_expense_by_id,
    delete_income_by_id,
    find_user_by_email,
    find_user_by_id,
    get_active_categories,
    get_admin_overview,
    get_advanced_analytics,
    get_all_categories,
    get_all_users,
    get_budget_status,
    get_dashboard_analytics,
    get_dashboard_summary,
    get_expense_by_id,
    get_filtered_expenses,
    get_filtered_incomes,
    get_income_by_id,
    get_recurring_transaction_by_id,
    get_recurring_transactions,
    get_report_summary,
    get_category_by_id,
    init_db,
    month_label,
    restore_user_backup_payload,
    seed_db,
    update_recurring_transaction,
    update_category,
    update_expense_by_id,
    update_income_by_id,
    update_user_password,
    update_user_profile,
    update_user_role,
    upsert_budget,
)


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config:
        app.config.update(test_config)

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = find_user_by_id(user_id) if user_id else None
        g.recurring_updates = 0
        if g.user:
            g.recurring_updates = apply_due_recurring_transactions(g.user["id"])

    @app.context_processor
    def inject_globals():
        return {
            "current_year": datetime.now().year,
            "demo_email": app.config["DEMO_EMAIL"],
            "demo_password": app.config["DEMO_PASSWORD"],
        }

    def login_required(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if g.user is None:
                flash("Please sign in to continue.", "error")
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped_view

    def admin_required(view):
        @wraps(view)
        @login_required
        def wrapped_view(*args, **kwargs):
            if g.user["role"] != "admin":
                flash("Admin access is required for that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)

        return wrapped_view

    @app.route("/")
    def landing():
        if g.user:
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.route("/health")
    def health():
        try:
            conn = sqlite3.connect(app.config["DATABASE_PATH"])
            conn.execute("SELECT 1")
            conn.close()
            return jsonify({"status": "ok"}), 200
        except sqlite3.Error:
            return jsonify({"status": "degraded"}), 503

    @app.route("/register", methods=("GET", "POST"))
    def register():
        if g.user:
            return redirect(url_for("dashboard"))

        error = None
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not name:
                error = "Full name is required."
            elif not email:
                error = "Email address is required."
            elif len(password) < 8:
                error = "Password must be at least 8 characters long."
            elif find_user_by_email(email):
                error = "An account with that email already exists."
            else:
                user_id = create_user(name, email, generate_password_hash(password))
                session.clear()
                session["user_id"] = user_id
                flash("Your account has been created.", "success")
                return redirect(url_for("dashboard"))

        return render_template("register.html", error=error)

    @app.route("/login", methods=("GET", "POST"))
    def login():
        if g.user:
            return redirect(url_for("dashboard"))

        error = None
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = find_user_by_email(email)

            if user is None or not check_password_hash(user["password_hash"], password):
                error = "Invalid email or password."
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash(f"Welcome back, {user['name'].split()[0]}.", "success")
                return redirect(url_for("dashboard"))

        return render_template("login.html", error=error)

    @app.route("/logout")
    def logout():
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("landing"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        filters = base_filters()
        categories = category_names()
        expenses = get_filtered_expenses(g.user["id"], **filters["expense_query"])
        incomes = get_filtered_incomes(g.user["id"], **filters["income_query"])
        summary = get_dashboard_summary(g.user["id"], expenses=expenses, incomes=incomes, budget_month=filters["budget_month"])
        budget_status = get_budget_status(
            g.user["id"],
            filters["budget_month"],
            threshold=current_app.config["BUDGET_ALERT_THRESHOLD"],
        )
        analytics = get_dashboard_analytics(g.user["id"], filters["budget_month"])
        advanced_analytics = get_advanced_analytics(g.user["id"], filters["budget_month"])

        return render_template(
            "dashboard.html",
            expenses=expenses,
            incomes=incomes,
            summary=summary,
            budget_status=budget_status,
            analytics=analytics,
            advanced_analytics=advanced_analytics,
            filters=filters,
            categories=categories,
            budget_month_label=month_label(filters["budget_month"]),
        )

    @app.route("/incomes")
    @login_required
    def incomes():
        filters = base_filters()
        incomes_list = get_filtered_incomes(g.user["id"], **filters["income_query"])
        return render_template("incomes.html", incomes=incomes_list, filters=filters)

    @app.route("/incomes/add", methods=("GET", "POST"))
    @login_required
    def add_income():
        if request.method == "POST":
            form_data, error = validate_income_form(request.form)
            if error:
                return render_template("income_form.html", error=error, form_data=form_data, is_edit=False)
            create_income(g.user["id"], **form_data)
            flash("Income added successfully.", "success")
            return redirect(url_for("incomes"))
        return render_template("income_form.html", form_data=default_income_form_data(), is_edit=False)

    @app.route("/incomes/<int:income_id>/edit", methods=("GET", "POST"))
    @login_required
    def edit_income(income_id):
        income = get_income_by_id(income_id, g.user["id"])
        if income is None:
            flash("Income record not found.", "error")
            return redirect(url_for("incomes"))
        if request.method == "POST":
            form_data, error = validate_income_form(request.form)
            if error:
                return render_template("income_form.html", error=error, form_data=form_data, is_edit=True, income=income)
            update_income_by_id(income_id, g.user["id"], **form_data)
            flash("Income updated successfully.", "success")
            return redirect(url_for("incomes"))
        return render_template("income_form.html", form_data=income_to_form_data(income), is_edit=True, income=income)

    @app.route("/incomes/<int:income_id>/delete", methods=("POST",))
    @login_required
    def delete_income(income_id):
        if delete_income_by_id(income_id, g.user["id"]):
            flash("Income deleted.", "success")
        else:
            flash("Income record not found.", "error")
        return redirect(url_for("incomes"))

    @app.route("/expenses/add", methods=("GET", "POST"))
    @login_required
    def add_expense():
        categories = category_names()
        if request.method == "POST":
            form_data, error = validate_expense_form(request.form, categories)
            if error:
                return render_template("expense_form.html", error=error, form_data=form_data, is_edit=False, categories=categories)
            create_expense(g.user["id"], **form_data)
            flash("Expense added successfully.", "success")
            return redirect(url_for("dashboard"))
        return render_template("expense_form.html", form_data=default_expense_form_data(categories), is_edit=False, categories=categories)

    @app.route("/expenses/<int:expense_id>/edit", methods=("GET", "POST"))
    @login_required
    def edit_expense(expense_id):
        categories = category_names()
        expense = get_expense_by_id(expense_id, g.user["id"])
        if expense is None:
            flash("Expense not found.", "error")
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            form_data, error = validate_expense_form(request.form, categories)
            if error:
                return render_template("expense_form.html", error=error, form_data=form_data, is_edit=True, expense=expense, categories=categories)
            update_expense_by_id(expense_id, g.user["id"], **form_data)
            flash("Expense updated successfully.", "success")
            return redirect(url_for("dashboard"))
        return render_template("expense_form.html", form_data=expense_to_form_data(expense), is_edit=True, expense=expense, categories=categories)

    @app.route("/expenses/<int:expense_id>/delete", methods=("POST",))
    @login_required
    def delete_expense(expense_id):
        if delete_expense_by_id(expense_id, g.user["id"]):
            flash("Expense deleted.", "success")
        else:
            flash("Expense not found.", "error")
        return redirect(url_for("dashboard"))

    @app.route("/budgets", methods=("POST",))
    @login_required
    def set_budget():
        categories = category_names()
        budget_data, error = validate_budget_form(request.form, categories)
        if error:
            flash(error, "error")
            return redirect(url_for("dashboard", budget_month=request.form.get("month", default_budget_month())))
        upsert_budget(g.user["id"], budget_data["category"], budget_data["month"], budget_data["amount"])
        flash(f"{budget_data['category']} budget saved for {month_label(budget_data['month'])}.", "success")
        return redirect(url_for("dashboard", budget_month=budget_data["month"]))

    @app.route("/reports")
    @login_required
    def reports():
        year = request.args.get("year", datetime.now().strftime("%Y"))
        if not year.isdigit():
            year = datetime.now().strftime("%Y")
        report = get_report_summary(g.user["id"], year)
        return render_template("reports.html", report=report, selected_year=year)

    @app.route("/reports/download/pdf")
    @login_required
    def download_report_pdf():
        year = request.args.get("year", datetime.now().strftime("%Y"))
        if not year.isdigit():
            year = datetime.now().strftime("%Y")
        report = get_report_summary(g.user["id"], year)
        pdf_bytes = build_report_pdf(report, g.user["name"])
        filename = f"spendly-report-{year}.pdf"
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.route("/recurring")
    @login_required
    def recurring():
        rules = get_recurring_transactions(g.user["id"])
        return render_template("recurring.html", rules=rules, categories=category_names(), recurring_form_data=default_recurring_form_data(category_names()))

    @app.route("/recurring/add", methods=("POST",))
    @login_required
    def add_recurring():
        categories = category_names()
        form_data, error = validate_recurring_form(request.form, categories)
        if error:
            flash(error, "error")
            return render_template("recurring.html", rules=get_recurring_transactions(g.user["id"]), categories=categories, recurring_form_data=form_data)
        create_recurring_transaction(g.user["id"], **form_data)
        flash("Recurring transaction saved.", "success")
        return redirect(url_for("recurring"))

    @app.route("/recurring/<int:rule_id>/edit", methods=("GET", "POST"))
    @login_required
    def edit_recurring(rule_id):
        categories = category_names()
        rule = get_recurring_transaction_by_id(rule_id, g.user["id"])
        if rule is None:
            flash("Recurring rule not found.", "error")
            return redirect(url_for("recurring"))
        if request.method == "POST":
            form_data, error = validate_recurring_form(request.form, categories)
            if error:
                return render_template("recurring_edit.html", rule=rule, recurring_form_data=form_data, categories=categories, error=error)
            update_recurring_transaction(rule_id, g.user["id"], **form_data)
            flash("Recurring transaction updated.", "success")
            return redirect(url_for("recurring"))
        return render_template("recurring_edit.html", rule=rule, recurring_form_data=recurring_rule_to_form_data(rule), categories=categories, error=None)

    @app.route("/recurring/<int:rule_id>/delete", methods=("POST",))
    @login_required
    def delete_recurring(rule_id):
        from database.db import delete_recurring_transaction
        if delete_recurring_transaction(rule_id, g.user["id"]):
            flash("Recurring transaction removed.", "success")
        else:
            flash("Recurring rule not found.", "error")
        return redirect(url_for("recurring"))

    @app.route("/profile", methods=("GET", "POST"))
    @login_required
    def profile():
        profile_error = None
        password_error = None

        if request.method == "POST":
            action = request.form.get("action")
            if action == "profile":
                name = request.form.get("name", "").strip()
                email = request.form.get("email", "").strip().lower()
                if not name:
                    profile_error = "Name is required."
                elif not email:
                    profile_error = "Email is required."
                else:
                    existing_user = find_user_by_email(email)
                    if existing_user and existing_user["id"] != g.user["id"]:
                        profile_error = "That email address is already in use."
                    else:
                        update_user_profile(g.user["id"], name, email)
                        flash("Profile updated successfully.", "success")
                        return redirect(url_for("profile"))

            if action == "password":
                current_password = request.form.get("current_password", "")
                new_password = request.form.get("new_password", "")
                confirm_password = request.form.get("confirm_password", "")
                if not check_password_hash(g.user["password_hash"], current_password):
                    password_error = "Current password is incorrect."
                elif len(new_password) < 8:
                    password_error = "New password must be at least 8 characters long."
                elif new_password != confirm_password:
                    password_error = "New password and confirmation must match."
                else:
                    update_user_password(g.user["id"], generate_password_hash(new_password))
                    flash("Password updated successfully.", "success")
                    return redirect(url_for("profile"))

        fresh_user = find_user_by_id(g.user["id"])
        return render_template("profile.html", profile_error=profile_error, password_error=password_error, profile_user=fresh_user)

    @app.route("/data/backup")
    @login_required
    def backup_data():
        payload = build_user_backup_payload(g.user["id"])
        filename = f"spendly-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.route("/data/restore", methods=("POST",))
    @login_required
    def restore_data():
        backup_file = request.files.get("backup_file")
        payload, error = parse_backup_upload(backup_file)
        if error:
            flash(error, "error")
            return redirect(url_for("profile"))

        restore_user_backup_payload(g.user["id"], payload)
        flash("Backup restored successfully.", "success")
        return redirect(url_for("dashboard"))

    @app.route("/admin")
    @admin_required
    def admin_dashboard():
        overview = get_admin_overview()
        users = get_all_users()
        categories = get_all_categories()
        return render_template("admin_dashboard.html", overview=overview, users=users, categories=categories)

    @app.route("/admin/users/<int:user_id>/role", methods=("POST",))
    @admin_required
    def admin_update_user_role(user_id):
        role = request.form.get("role", "user")
        if role not in {"user", "admin"}:
            flash("Invalid role selected.", "error")
            return redirect(url_for("admin_dashboard"))
        update_user_role(user_id, role)
        flash("User role updated.", "success")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/categories/create", methods=("POST",))
    @admin_required
    def admin_create_category():
        name = request.form.get("name", "").strip()
        error = validate_category_name(name)
        if error:
            flash(error, "error")
        else:
            try:
                create_category(name, created_by_user_id=g.user["id"])
                flash("Category created.", "success")
            except Exception:
                flash("That category already exists.", "error")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/categories/<int:category_id>/update", methods=("POST",))
    @admin_required
    def admin_update_category(category_id):
        name = request.form.get("name", "").strip()
        is_active = request.form.get("is_active") == "1"
        error = validate_category_name(name)
        if error:
            flash(error, "error")
            return redirect(url_for("admin_dashboard"))
        try:
            if update_category(category_id, name, is_active):
                flash("Category updated.", "success")
            else:
                flash("Category not found.", "error")
        except Exception:
            flash("Could not update category. That name may already exist.", "error")
        return redirect(url_for("admin_dashboard"))

    @app.route("/admin/categories/<int:category_id>/delete", methods=("POST",))
    @admin_required
    def admin_delete_category(category_id):
        category = get_category_by_id(category_id)
        if category and category["is_default"]:
            flash("Default categories cannot be deleted.", "error")
        elif delete_category(category_id):
            flash("Category archived.", "success")
        else:
            flash("Category not found.", "error")
        return redirect(url_for("admin_dashboard"))

    @app.route("/expenses/export")
    @login_required
    def export_expenses():
        filters = base_filters()
        expenses = get_filtered_expenses(g.user["id"], **filters["expense_query"])
        csv_content = build_expense_csv(expenses)
        filename = f"spendly-expenses-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv"
        if request.args.get("download") == "1":
            return Response(csv_content, mimetype="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
        return render_template("export_preview.html", csv_content=csv_content, filename=filename, filters=filters, expense_count=len(expenses))

    @app.route("/expenses/import", methods=("POST",))
    @login_required
    def import_expenses():
        rows, error = parse_csv_upload(request.files.get("csv_file"), category_names())
        if error:
            flash(error, "error")
            return redirect(url_for("dashboard", budget_month=request.form.get("budget_month", default_budget_month())))
        create_expense_batch(g.user["id"], rows)
        flash(f"Imported {len(rows)} expenses from CSV.", "success")
        return redirect(url_for("dashboard", budget_month=request.form.get("budget_month", default_budget_month())))

    @app.route("/privacy")
    def privacy():
        return render_template("privacy.html")

    @app.route("/terms")
    def terms():
        return render_template("terms.html")

    with app.app_context():
        init_db()
        if not app.config.get("TESTING"):
            seed_db()

    return app


def category_names():
    return [row["name"] for row in get_active_categories()]


def base_filters():
    budget_month = normalize_month(request.args.get("budget_month", default_budget_month()).strip())
    search = request.args.get("search", "").strip()
    min_amount = parse_optional_float(request.args.get("min_amount", "").strip())
    max_amount = parse_optional_float(request.args.get("max_amount", "").strip())
    source = request.args.get("source", "").strip()
    category = request.args.get("category", "").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()

    return {
        "category": category,
        "source": source,
        "start_date": start_date,
        "end_date": end_date,
        "search": search,
        "min_amount": request.args.get("min_amount", "").strip(),
        "max_amount": request.args.get("max_amount", "").strip(),
        "budget_month": budget_month,
        "expense_query": {
            "category": category or None,
            "start_date": start_date or None,
            "end_date": end_date or None,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "search": search or None,
        },
        "income_query": {
            "source": f"%{source}%" if source else None,
            "start_date": start_date or None,
            "end_date": end_date or None,
            "min_amount": min_amount,
            "max_amount": max_amount,
            "search": search or None,
        },
    }


def parse_optional_float(value):
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def default_expense_form_data(categories):
    return {
        "amount": "",
        "category": categories[0] if categories else "",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": "",
    }


def default_income_form_data():
    return {
        "amount": "",
        "source": "Salary",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "description": "",
    }


def default_recurring_form_data(categories):
    today = datetime.now().strftime("%Y-%m-%d")
    return {
        "kind": "expense",
        "title": "",
        "amount": "",
        "category": categories[0] if categories else "",
        "source": "Salary",
        "cadence": "monthly",
        "start_date": today,
        "next_run_date": today,
        "end_date": "",
        "description": "",
        "is_active": True,
    }


def expense_to_form_data(expense):
    return {
        "amount": f"{expense['amount']:.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }


def income_to_form_data(income):
    return {
        "amount": f"{income['amount']:.2f}",
        "source": income["source"],
        "date": income["date"],
        "description": income["description"] or "",
    }


def recurring_rule_to_form_data(rule):
    return {
        "kind": rule["kind"],
        "title": rule["title"],
        "amount": f"{rule['amount']:.2f}",
        "category": rule["category"] or "",
        "source": rule["source"] or "",
        "cadence": rule["cadence"],
        "start_date": rule["start_date"],
        "next_run_date": rule["next_run_date"],
        "end_date": rule["end_date"] or "",
        "description": rule["description"] or "",
        "is_active": bool(rule["is_active"]),
    }


def validate_money_and_date(form_data):
    try:
        amount = float(form_data["amount"])
    except ValueError:
        return None, "Amount must be a valid number."

    if amount <= 0:
        return None, "Amount must be greater than zero."

    try:
        datetime.strptime(form_data["date"], "%Y-%m-%d")
    except ValueError:
        return None, "Date must be in YYYY-MM-DD format."

    if len(form_data["description"]) > 120:
        return None, "Description must be 120 characters or fewer."

    return amount, None


def validate_expense_form(form, categories):
    form_data = {
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }
    amount, error = validate_money_and_date(form_data)
    if error:
        return form_data, error
    if form_data["category"] not in categories:
        return form_data, "Please choose a valid category."
    form_data["amount"] = amount
    return form_data, None


def validate_income_form(form):
    form_data = {
        "amount": form.get("amount", "").strip(),
        "source": form.get("source", "").strip(),
        "date": form.get("date", "").strip(),
        "description": form.get("description", "").strip(),
    }
    amount, error = validate_money_and_date(form_data)
    if error:
        return form_data, error
    if not form_data["source"]:
        return form_data, "Income source is required."
    form_data["amount"] = amount
    return form_data, None


def default_budget_month():
    return datetime.now().strftime("%Y-%m")


def normalize_month(value):
    try:
        return datetime.strptime(value, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return default_budget_month()


def validate_budget_form(form, categories):
    category = form.get("category", "").strip()
    month = form.get("month", "").strip()
    amount_raw = form.get("amount", "").strip()

    if category not in categories:
        return None, "Please choose a valid budget category."
    try:
        normalized_month = datetime.strptime(month, "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return None, "Budget month must be in YYYY-MM format."
    try:
        amount = float(amount_raw)
    except ValueError:
        return None, "Budget amount must be a valid number."
    if amount <= 0:
        return None, "Budget amount must be greater than zero."
    return {"category": category, "month": normalized_month, "amount": amount}, None


def validate_category_name(name):
    if not name:
        return "Category name is required."
    if len(name) > 40:
        return "Category name must be 40 characters or fewer."
    return None


def validate_recurring_form(form, categories):
    form_data = {
        "kind": form.get("kind", "").strip(),
        "title": form.get("title", "").strip(),
        "amount": form.get("amount", "").strip(),
        "category": form.get("category", "").strip(),
        "source": form.get("source", "").strip(),
        "cadence": form.get("cadence", "").strip(),
        "start_date": form.get("start_date", "").strip(),
        "next_run_date": form.get("next_run_date", "").strip(),
        "end_date": form.get("end_date", "").strip() or None,
        "description": form.get("description", "").strip(),
        "is_active": form.get("is_active", "1") == "1",
    }

    if form_data["kind"] not in {"expense", "income"}:
        return form_data, "Recurring type must be income or expense."
    if not form_data["title"]:
        return form_data, "Recurring title is required."
    if form_data["cadence"] not in {"weekly", "monthly", "quarterly", "yearly"}:
        return form_data, "Please choose a valid recurrence cadence."

    amount, error = validate_money_and_date(
        {
            "amount": form_data["amount"],
            "date": form_data["start_date"],
            "description": form_data["description"],
        }
    )
    if error:
        return form_data, error

    try:
        datetime.strptime(form_data["next_run_date"], "%Y-%m-%d")
    except ValueError:
        return form_data, "Next run date must be in YYYY-MM-DD format."

    if form_data["end_date"]:
        try:
            datetime.strptime(form_data["end_date"], "%Y-%m-%d")
        except ValueError:
            return form_data, "End date must be in YYYY-MM-DD format."

    if form_data["kind"] == "expense":
        if form_data["category"] not in categories:
            return form_data, "Please choose a valid category for recurring expenses."
        form_data["source"] = None
    else:
        if not form_data["source"]:
            return form_data, "Income source is required for recurring income."
        form_data["category"] = None

    form_data["amount"] = amount
    return form_data, None


def parse_csv_upload(csv_file, categories):
    if csv_file is None or not csv_file.filename:
        return None, "Please choose a CSV file to import."
    try:
        content = csv_file.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return None, "CSV file must be UTF-8 encoded."

    reader = csv.DictReader(io.StringIO(content))
    expected_fields = {"date", "category", "amount", "description"}
    if reader.fieldnames is None:
        return None, "CSV file is empty."
    normalized_fields = {field.strip().lower() for field in reader.fieldnames}
    if not expected_fields.issubset(normalized_fields):
        return None, "CSV must include date, category, amount, and description columns."

    rows = []
    for index, row in enumerate(reader, start=2):
        if len(rows) >= current_app.config["CSV_MAX_IMPORT_ROWS"]:
            return None, f"CSV import limit is {current_app.config['CSV_MAX_IMPORT_ROWS']} rows."
        normalized_row = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
        if not any(normalized_row.values()):
            continue
        parsed_row, error = validate_expense_form(
            {
                "amount": normalized_row.get("amount", ""),
                "category": normalized_row.get("category", ""),
                "date": normalized_row.get("date", ""),
                "description": normalized_row.get("description", ""),
            },
            categories,
        )
        if error:
            return None, f"Row {index}: {error}"
        rows.append(parsed_row)
    if not rows:
        return None, "CSV did not contain any valid expense rows."
    return rows, None


def build_expense_csv(expenses):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "category", "amount", "description"])
    for expense in expenses:
        writer.writerow([expense["date"], expense["category"], f"{expense['amount']:.2f}", expense["description"] or ""])
    return output.getvalue()


def parse_backup_upload(backup_file):
    if backup_file is None or not backup_file.filename:
        return None, "Please choose a backup file to restore."

    try:
        payload = json.loads(backup_file.stream.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, "Backup file must be valid UTF-8 JSON."

    required_keys = {"expenses", "incomes", "budgets", "recurring_transactions"}
    if not required_keys.issubset(payload.keys()):
        return None, "Backup file is missing required sections."

    return payload, None


def build_report_pdf(report, user_name):
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 50

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(40, y, f"Spendly Financial Report - {report['year']}")
    y -= 24

    pdf.setFont("Helvetica", 11)
    pdf.drawString(40, y, f"Prepared for: {user_name}")
    y -= 18
    pdf.drawString(40, y, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 28

    summary_lines = [
        f"Yearly income: Rs {report['total_income']:.2f}",
        f"Yearly expenses: Rs {report['total_expense']:.2f}",
        f"Net total: Rs {report['net_total']:.2f}",
    ]
    for line in summary_lines:
        pdf.drawString(40, y, line)
        y -= 16

    y -= 10
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(40, y, "Monthly breakdown")
    y -= 20

    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(40, y, "Month")
    pdf.drawString(170, y, "Income")
    pdf.drawString(280, y, "Expenses")
    pdf.drawString(390, y, "Net")
    y -= 14
    pdf.line(40, y, width - 40, y)
    y -= 12

    pdf.setFont("Helvetica", 10)
    for item in report["monthly"]:
        if y < 60:
            pdf.showPage()
            y = height - 50
            pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y, item["label"])
        pdf.drawString(170, y, f"Rs {item['income_total']:.2f}")
        pdf.drawString(280, y, f"Rs {item['expense_total']:.2f}")
        pdf.drawString(390, y, f"Rs {item['net_total']:.2f}")
        y -= 16

    pdf.save()
    return buffer.getvalue()


app = create_app()


if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"], port=app.config["PORT"])
