from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import csv
import io
app = Flask(__name__)

def clean_money_input(value):
    if not value:
        return 0

    return float(value.replace(",", "").strip())

# Basic app settings
app.config["SECRET_KEY"] = "change-this-secret-key-later"

# SQLite database setup
basedir = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(basedir, "database.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Login manager setup
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message_category = "warning"


# User table/model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    type = db.Column(db.String(20), nullable=False)  # income or expense
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    transaction_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Float, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email").lower().strip()
        password = request.form.get("password")

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email already registered. Please log in instead.", "danger")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        new_user = User(
            name=name,
            email=email,
            password_hash=password_hash
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").lower().strip()
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/dashboard")
@login_required
def dashboard():
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    monthly_income = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    monthly_expense = db.session.query(db.func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    balance = monthly_income - monthly_expense

    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.transaction_date.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        monthly_income=monthly_income,
        monthly_expense=monthly_expense,
        balance=balance,
        recent_transactions=recent_transactions
    )

@app.route("/transactions")
@login_required
def transactions():
    transaction_type = request.args.get("type", "all")
    selected_month = request.args.get("month", "")

    query = Transaction.query.filter_by(user_id=current_user.id)

    if transaction_type in ["income", "expense"]:
        query = query.filter(Transaction.type == transaction_type)

    if selected_month:
        try:
            selected_date = datetime.strptime(selected_month, "%Y-%m").date()
            start_date = selected_date.replace(day=1)

            if start_date.month == 12:
                next_month = start_date.replace(
                    year=start_date.year + 1,
                    month=1,
                    day=1
                )
            else:
                next_month = start_date.replace(
                    month=start_date.month + 1,
                    day=1
                )

            query = query.filter(
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date < next_month
            )

        except ValueError:
            flash("Invalid month selected.", "danger")
            return redirect(url_for("transactions"))

    user_transactions = query.order_by(
        Transaction.transaction_date.desc()
    ).all()

    return render_template(
        "transactions.html",
        transactions=user_transactions,
        selected_type=transaction_type,
        selected_month=selected_month
    )


@app.route("/transactions/add", methods=["GET", "POST"])
@login_required
def add_transaction():
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    monthly_income = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    monthly_expense = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    balance = monthly_income - monthly_expense

    current_budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=today.month,
        year=today.year
    ).first()

    budget_amount = current_budget.amount if current_budget else 0

    if budget_amount > 0:
        percentage_used = (monthly_expense / budget_amount) * 100
    else:
       percentage_used = 0

    progress_width = min(percentage_used, 100)

    if request.method == "POST":
        transaction_type = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        transaction_date = request.form.get("transaction_date")

        try:
           amount = clean_money_input(amount)
        except ValueError:
            flash("Please enter a valid amount.", "danger")
            return redirect(url_for("add_transaction"))

        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(url_for("add_transaction"))

        if transaction_type not in ["income", "expense"]:
            flash("Please select either income or expense.", "danger")
            return redirect(url_for("add_transaction"))

        try:
            transaction_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Please select a valid date.", "danger")
            return redirect(url_for("add_transaction"))

        new_transaction = Transaction(
            user_id=current_user.id,
            type=transaction_type,
            amount=amount,
            category=category,
            description=description,
            transaction_date=transaction_date
        )

        db.session.add(new_transaction)
        db.session.commit()

        flash("Transaction added successfully.", "success")
        return redirect(url_for("transactions"))

    return render_template(
    "add_transaction.html",
    today=today.isoformat(),
    monthly_income=monthly_income,
    monthly_expense=monthly_expense,
    balance=balance,
    current_budget=current_budget,
    budget_amount=budget_amount,
    percentage_used=percentage_used,
    progress_width=progress_width
)


@app.route("/transactions/edit/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":
        transaction_type = request.form.get("type")
        amount = request.form.get("amount")
        category = request.form.get("category")
        description = request.form.get("description")
        transaction_date = request.form.get("transaction_date")

        try:
            amount = float(amount)
        except ValueError:
            flash("Please enter a valid amount.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction.id))

        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction.id))

        if transaction_type not in ["income", "expense"]:
            flash("Please select either income or expense.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction.id))

        try:
            transaction_date = datetime.strptime(transaction_date, "%Y-%m-%d").date()
        except ValueError:
            flash("Please select a valid date.", "danger")
            return redirect(url_for("edit_transaction", transaction_id=transaction.id))

        transaction.type = transaction_type
        transaction.amount = amount
        transaction.category = category
        transaction.description = description
        transaction.transaction_date = transaction_date

        db.session.commit()

        flash("Transaction updated successfully.", "success")
        return redirect(url_for("transactions"))

    return render_template("edit_transaction.html", transaction=transaction)


@app.route("/transactions/delete/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):
    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(transaction)
    db.session.commit()

    flash("Transaction deleted successfully.", "info")
    return redirect(url_for("transactions"))

@app.route("/reports")
@login_required
def reports():
    selected_month = request.args.get("month", datetime.utcnow().strftime("%Y-%m"))

    try:
        month_start = datetime.strptime(selected_month, "%Y-%m").date()
    except ValueError:
        month_start = datetime.utcnow().date().replace(day=1)
        selected_month = month_start.strftime("%Y-%m")

    # Find the first day of the next month
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1)

    # Find the previous month
    if month_start.month == 1:
        previous_month_start = month_start.replace(year=month_start.year - 1, month=12, day=1)
    else:
        previous_month_start = month_start.replace(month=month_start.month - 1, day=1)

    previous_month_end = month_start

    # This month income
    total_income = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).scalar() or 0

    # This month expenses
    total_expenses = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).scalar() or 0

    # Previous month income
    previous_income = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.transaction_date >= previous_month_start,
        Transaction.transaction_date < previous_month_end
    ).scalar() or 0

    # Previous month expenses
    previous_expenses = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= previous_month_start,
        Transaction.transaction_date < previous_month_end
    ).scalar() or 0

    net_savings = total_income - total_expenses
    previous_savings = previous_income - previous_expenses

    if total_income > 0:
        savings_rate = (net_savings / total_income) * 100
    else:
        savings_rate = 0

    if previous_income > 0:
        previous_savings_rate = (previous_savings / previous_income) * 100
    else:
        previous_savings_rate = 0

    def calculate_change(current, previous):
        if previous == 0:
            return 0

        return ((current - previous) / previous) * 100

    income_change = calculate_change(total_income, previous_income)
    expense_change = calculate_change(total_expenses, previous_expenses)
    savings_change = calculate_change(net_savings, previous_savings)
    savings_rate_change = savings_rate - previous_savings_rate
    
    trend_labels = []
    trend_income = []
    trend_expenses = []

    for i in range(5, -1, -1):
        trend_month = month_start.month - i
        trend_year = month_start.year

        while trend_month <= 0:
            trend_month += 12
            trend_year -= 1

        trend_start = datetime(trend_year, trend_month, 1).date()

        if trend_month == 12:
            trend_end = datetime(trend_year + 1, 1, 1).date()
        else:
            trend_end = datetime(trend_year, trend_month + 1, 1).date()

        income_total = db.session.query(
            db.func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == "income",
            Transaction.transaction_date >= trend_start,
            Transaction.transaction_date < trend_end
        ).scalar() or 0

        expense_total = db.session.query(
            db.func.sum(Transaction.amount)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.type == "expense",
            Transaction.transaction_date >= trend_start,
            Transaction.transaction_date < trend_end
        ).scalar() or 0

        trend_labels.append(trend_start.strftime("%b %Y"))
        trend_income.append(float(income_total))
        trend_expenses.append(float(expense_total))
    
        category_rows = db.session.query(
        Transaction.category,
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date < month_end
    ).group_by(Transaction.category).order_by(db.func.sum(Transaction.amount).desc()).all()

    category_labels = [row[0] for row in category_rows]
    category_values = [float(row[1]) for row in category_rows]
    category_total = sum(category_values)

    category_colors = [
        "#f97316",
        "#3b82f6",
        "#a855f7",
        "#facc15",
        "#22c55e",
        "#9ca3af",
        "#fb7185",
        "#14b8a6"
    ]

    category_items = []

    for index, row in enumerate(category_rows):
        category_name = row[0]
        category_amount = float(row[1])

        if category_total > 0:
            category_percentage = (category_amount / category_total) * 100
        else:
            category_percentage = 0

        category_items.append({
            "name": category_name,
            "amount": category_amount,
            "percentage": category_percentage,
            "color": category_colors[index % len(category_colors)]
        })

    if trend_expenses:
        non_zero_expenses = [
        (label, amount)
        for label, amount in zip(trend_labels, trend_expenses)
            if amount > 0
        ]

        if non_zero_expenses:
            active_expense_amounts = [amount for label, amount in non_zero_expenses]

            average_monthly_expense = sum(active_expense_amounts) / len(active_expense_amounts)

            highest_month_label, highest_expense = max(
                non_zero_expenses,
                key=lambda item: item[1]
            )

            lowest_month_label, lowest_expense = min(
                non_zero_expenses,
                key=lambda item: item[1]
            )
        else:
            average_monthly_expense = 0
            highest_expense = 0
            highest_month_label = "N/A"
            lowest_expense = 0
            lowest_month_label = "N/A"
    else:
        average_monthly_expense = 0
        highest_expense = 0
        highest_month_label = "N/A"
        lowest_expense = 0
        lowest_month_label = "N/A"
        average_monthly_expense = 0
        highest_expense = 0
        highest_month_label = "N/A"
        lowest_expense = 0
        lowest_month_label = "N/A"

    if total_income == 0 and total_expenses == 0:
        insight_text = "No income or expenses recorded for this month yet. Add transactions to see useful insights."
    elif net_savings > 0:
        insight_text = "Your income is higher than your expenses this month. Keep tracking daily to maintain a healthy savings rate."
    elif net_savings == 0:
        insight_text = "Your income and expenses are balanced this month. Try reducing small expenses to increase your savings."
    else:
        insight_text = "Your expenses are higher than your income this month. Review your top spending categories and adjust your budget."

    month_label = month_start.strftime("%B %Y")
        
    return render_template(
    "reports.html",
    selected_month=selected_month,
    month_label=month_label,
    total_income=total_income,
    total_expenses=total_expenses,
    net_savings=net_savings,
    savings_rate=savings_rate,
    income_change=income_change,
    expense_change=expense_change,
    savings_change=savings_change,
    savings_rate_change=savings_rate_change,
    trend_labels=trend_labels,
    trend_income=trend_income,
    trend_expenses=trend_expenses,
    category_labels=category_labels,
    category_values=category_values,
    category_total=category_total,
    category_items=category_items,
    category_colors=category_colors,
    average_monthly_expense=average_monthly_expense,
    highest_month_label=highest_month_label,
    highest_expense=highest_expense,
    lowest_month_label=lowest_month_label,
    lowest_expense=lowest_expense,
    insight_text=insight_text

)

@app.route("/api/reports/summary")
@login_required
def reports_summary():
    today = datetime.utcnow().date()
    month_start = today.replace(day=1)

    category_rows = db.session.query(
        Transaction.category,
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).group_by(Transaction.category).all()

    category_labels = [row[0] for row in category_rows]
    category_values = [float(row[1]) for row in category_rows]

    monthly_income = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    monthly_expense = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    return {
        "category_labels": category_labels,
        "category_values": category_values,
        "income_expense_labels": ["Income", "Expenses"],
        "income_expense_values": [float(monthly_income), float(monthly_expense)]
    }


@app.route("/budget", methods=["GET", "POST"])
@login_required
def budget():
    today = datetime.utcnow().date()
    current_month = today.month
    current_year = today.year
    month_start = today.replace(day=1)

    if request.method == "POST":
        amount = request.form.get("amount")

        try:
            amount = clean_money_input(amount)
        except ValueError:
            flash("Please enter a valid budget amount.", "danger")
            return redirect(url_for("budget"))

        if amount <= 0:
            flash("Budget amount must be greater than zero.", "danger")
            return redirect(url_for("budget"))

        existing_budget = Budget.query.filter_by(
            user_id=current_user.id,
            month=current_month,
            year=current_year
        ).first()

        if existing_budget:
            existing_budget.amount = amount
        else:
            new_budget = Budget(
                user_id=current_user.id,
                month=current_month,
                year=current_year,
                amount=amount
            )
            db.session.add(new_budget)

        db.session.commit()

        flash("Budget saved successfully.", "success")
        return redirect(url_for("budget"))

    current_budget = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month,
        year=current_year
    ).first()

    monthly_expense = db.session.query(
        db.func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        Transaction.transaction_date >= month_start,
        Transaction.transaction_date <= today
    ).scalar() or 0

    budget_amount = current_budget.amount if current_budget else 0
    remaining_budget = budget_amount - monthly_expense if current_budget else 0

    if budget_amount > 0:
        percentage_used = (monthly_expense / budget_amount) * 100
    else:
        percentage_used = 0

    return render_template(
        "budget.html",
        current_budget=current_budget,
        monthly_expense=monthly_expense,
        remaining_budget=remaining_budget,
        percentage_used=percentage_used
    )

@app.route("/export/csv")
@login_required
def export_csv():
    transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(Transaction.transaction_date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date",
        "Type",
        "Category",
        "Description",
        "Amount"
    ])

    for transaction in transactions:
        writer.writerow([
            transaction.transaction_date.strftime("%Y-%m-%d"),
            transaction.type,
            transaction.category,
            transaction.description or "",
            f"{transaction.amount:.2f}"
        ])

    csv_data = output.getvalue()

    response = Response(
        csv_data,
        mimetype="text/csv; charset=utf-8"
    )

    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    response.headers["X-Content-Type-Options"] = "nosniff"

    return response

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# Create database tables
with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)