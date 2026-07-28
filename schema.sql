DROP TABLE IF EXISTS salary;
DROP TABLE IF EXISTS employee;

CREATE TABLE employee (
    employee_id   SERIAL PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    email         TEXT UNIQUE NOT NULL,
    department    TEXT NOT NULL,
    job_title     TEXT NOT NULL,
    hire_date     DATE NOT NULL
);

CREATE TABLE salary (
    salary_id      SERIAL PRIMARY KEY,
    employee_id    INTEGER NOT NULL REFERENCES employee(employee_id),
    base_salary    NUMERIC(10,2) NOT NULL,
    bonus          NUMERIC(10,2) NOT NULL DEFAULT 0,
    currency       TEXT NOT NULL DEFAULT 'USD',
    effective_date DATE NOT NULL,
    end_date       DATE  -- NULL means currently active
);

INSERT INTO employee (first_name, last_name, email, department, job_title, hire_date) VALUES
('Alice',   'Nguyen',   'alice.nguyen@example.com',   'Engineering', 'Software Engineer',      '2019-03-11'),
('Ben',     'Carter',   'ben.carter@example.com',     'Engineering', 'Senior Software Engineer','2017-06-01'),
('Chloe',   'Martinez', 'chloe.martinez@example.com', 'Engineering', 'Engineering Manager',     '2015-01-20'),
('David',   'Kim',      'david.kim@example.com',      'Sales',       'Account Executive',       '2020-09-15'),
('Elena',   'Rossi',    'elena.rossi@example.com',    'Sales',       'Sales Manager',           '2016-11-03'),
('Farhan',  'Ahmed',    'farhan.ahmed@example.com',   'Finance',     'Financial Analyst',       '2021-02-08'),
('Grace',   'Liu',      'grace.liu@example.com',      'Finance',     'Finance Director',        '2014-07-22'),
('Hassan',  'Malik',    'hassan.malik@example.com',   'HR',          'HR Generalist',           '2022-04-18'),
('Isabella','Fernandez','isabella.fernandez@example.com','HR',       'HR Manager',              '2018-10-05'),
('Jack',    'Thompson', 'jack.thompson@example.com',  'Engineering', 'Software Engineer',       '2023-01-09');

-- Current salaries (end_date NULL)
INSERT INTO salary (employee_id, base_salary, bonus, effective_date, end_date) VALUES
(1, 95000.00,  5000.00, '2023-03-11', NULL),
(2, 125000.00, 10000.00,'2023-06-01', NULL),
(3, 155000.00, 15000.00,'2022-01-20', NULL),
(4, 70000.00,  8000.00, '2023-09-15', NULL),
(5, 110000.00, 12000.00,'2022-11-03', NULL),
(6, 75000.00,  3000.00, '2023-02-08', NULL),
(7, 145000.00, 14000.00,'2021-07-22', NULL),
(8, 62000.00,  2000.00, '2023-04-18', NULL),
(9, 98000.00,  6000.00, '2022-10-05', NULL),
(10,80000.00,  4000.00, '2023-01-09', NULL);

-- Salary history: Alice and Ben each had a prior, lower salary before their most recent raise
INSERT INTO salary (employee_id, base_salary, bonus, effective_date, end_date) VALUES
(1, 82000.00,  3000.00, '2019-03-11', '2023-03-10'),
(2, 108000.00, 8000.00, '2017-06-01', '2023-05-31');
