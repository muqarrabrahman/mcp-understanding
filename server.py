import json
import os
import pathlib

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("employee-salary-server")


def get_connection():
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def run_query(sql: str, params: tuple = ()) -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


@mcp.tool()
def list_employees(department: str | None = None) -> list[dict]:
    """List employees. If department is provided, only return employees in that department."""
    if department:
        return run_query(
            """
            SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
            FROM employee
            WHERE department ILIKE %s
            ORDER BY employee_id
            """,
            (department,),
        )
    return run_query(
        """
        SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
        FROM employee
        ORDER BY employee_id
        """
    )


@mcp.tool()
def get_employee(employee_id: int) -> list[dict]:
    """Get a single employee's details by their employee_id."""
    return run_query(
        """
        SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
        FROM employee
        WHERE employee_id = %s
        """,
        (employee_id,),
    )


@mcp.tool()
def search_employees(name_query: str) -> list[dict]:
    """Search employees by first or last name (partial match, case-insensitive)."""
    pattern = f"%{name_query}%"
    return run_query(
        """
        SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
        FROM employee
        WHERE first_name ILIKE %s OR last_name ILIKE %s
        ORDER BY employee_id
        """,
        (pattern, pattern),
    )


@mcp.tool()
def get_salary_history(employee_id: int) -> list[dict]:
    """Get the full salary history (all rows, past and current) for one employee, oldest first."""
    return run_query(
        """
        SELECT s.salary_id, s.employee_id, e.first_name, e.last_name,
               s.base_salary, s.bonus, s.currency, s.effective_date, s.end_date
        FROM salary s
        JOIN employee e ON e.employee_id = s.employee_id
        WHERE s.employee_id = %s
        ORDER BY s.effective_date
        """,
        (employee_id,),
    )


@mcp.tool()
def department_salary_summary() -> list[dict]:
    """Get average, minimum, and maximum current base salary per department."""
    return run_query(
        """
        SELECT e.department,
               COUNT(*) AS employee_count,
               ROUND(AVG(s.base_salary), 2) AS avg_salary,
               MIN(s.base_salary) AS min_salary,
               MAX(s.base_salary) AS max_salary
        FROM employee e
        JOIN salary s ON s.employee_id = e.employee_id
        WHERE s.end_date IS NULL
        GROUP BY e.department
        ORDER BY e.department
        """
    )


@mcp.resource("employees://all", mime_type="text/csv")
def all_employees_resource() -> str:
    """All employees as a CSV document (read-only context, not a callable action)."""
    rows = run_query(
        """
        SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
        FROM employee
        ORDER BY employee_id
        """
    )
    header = ",".join(rows[0].keys())
    lines = [",".join(str(v) for v in row.values()) for row in rows]
    return "\n".join([header] + lines)


@mcp.resource("company://info", mime_type="text/plain")
def company_info_resource() -> str:
    """Static company info document, read from disk (not from the DB)."""
    return pathlib.Path(__file__).parent.joinpath("company_info.txt").read_text()


@mcp.resource("employees://{employee_id}", mime_type="application/json")
def employee_resource(employee_id: str) -> str:
    """A single employee as a JSON document, addressed by employee_id in the URI."""
    rows = run_query(
        """
        SELECT employee_id, first_name, last_name, email, department, job_title, hire_date
        FROM employee
        WHERE employee_id = %s
        """,
        (int(employee_id),),
    )
    return json.dumps(rows[0] if rows else {}, default=str, indent=2)


@mcp.prompt()
def salary_review_prompt(employee_id: int) -> str:
    """Ready-made prompt: ask the LLM to review one employee's salary history and trend."""
    return (
        f"Look up employee {employee_id}'s salary history using the get_salary_history tool, "
        "then summarize their compensation trend: has it increased, by how much, and are there any notable raises."
    )


if __name__ == "__main__":
    mcp.run()
