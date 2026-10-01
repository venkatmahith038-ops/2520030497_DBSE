create database practice_db;
use practice_db;
create table students(
student_id INT PRIMARY KEY,
name varchar(50),
age INT,
department varchar(20),
city varchar(20),
marks int,
email varchar(100),
phone varchar(15)
);
describe students;
select * from students;
INSERT INTO students
(student_id, name, age, department, city, marks, email, phone)
VALUES
(1, 'Rahul', 20, 'CSE', 'Hyderabad', 85, 'rahul@gmail.com', '9876543210'),
(2, 'Priya', 19, 'ECE', 'Chennai', 72, 'priya@gmail.com', '9876543211'),
(3, 'Arjun', 21, 'CSE', 'Bangalore', 91, 'arjun@gmail.com', '9876543212'),
(4, 'Sneha', 20, 'IT', 'Hyderabad', 68, 'sneha@gmail.com', NULL),
(5, 'Kiran', 22, 'CSE', 'Mumbai', 95, 'kiran@gmail.com', '9876543214'),
(6, 'Anjali', 19, 'ECE', 'Hyderabad', 78, NULL, '9876543215'),
(7, 'Ravi', 23, 'MECH', 'Pune', 55, 'ravi@gmail.com', NULL),
(8, 'Neha', 21, 'IT', 'Chennai', 88, 'neha@gmail.com', '9876543217'),
(9, 'Vikram', 20, 'CSE', 'Delhi', 76, NULL, '9876543218'),
(10, 'Pooja', 22, 'ECE', 'Mumbai', 84, 'pooja@gmail.com', '9876543219');
select * from students;
select * from students where marks>80;
select* from students where marks<70;
select * from students where marks=85;
select * from students where marks>=80;
select * from students where marks<=70;
select * from students where department!='CSE';
select * from students where department = 'CSE' and marks>80;
select name, marks from students where marks>=85;
select * from students where city='Hyderabad' and marks>75;
select * from students where age>=21 and marks>80;
select * from students where department='CSE' and city='Hyderabad' and marks>80;
select * from  students where department='CSE' and marks between 80 and 95;
select * from students where department in('CSE','ECE') and marks>80;
select * from students where city='Hyderabad' and department='CSE' and marks>80;
select name,marks from students order by marks asc;
select name,age from students order by age asc;
select * from students order by name desc;
select * from students order by department asc;
select * from students order by department asc, marks asc;
select * from students order by department asc, marks desc;
select * from students order by city asc, marks desc;
select * from students where department='ECE' order by marks desc;
select * from students where city='Hyderabad' order by age asc;
select * from students where department in('CSE','ECE') order by name asc;
select * from students where city in('Hyderabad','Chennai') and marks>75 order by marks desc;
select * from students where department in('CSE','ECE','IT') and marks>=75 order by department asc, marks desc;
select * from students where department ='CSE' and marks>80 order by marks desc limit 2;
select * from students where city in('Hyderabad','Mumbai') and marks>75 order by marks desc limit 3;
select count(*) as total_students from students;
select sum(marks) as total_marks from students;
select avg(marks) as Average from students;
select min(marks), max(marks)  from students;
select sum(marks) from students where department='CSE';
select count(*) from students where city='Hyderabad';
select sum(marks) from students where city='Hyderabad';
select avg(marks) from students where department='CSE' and marks>80;
select sum(marks) from students where department in('CSE' or 'ECE');
select department from students group by department;
select city from students group by city;
select department, count(*) from students group by department;
select city, count(*) from students group by city;
select department, avg(marks) from students group by department;
select department, max(marks) from students group by department;
select city as City, min(marks) as Minimum  from students group by city;
select department, sum(marks) as Total from students group by department;
select department as Department, count(*) as Students, avg(marks) as Average from students group by department;
select department, sum(marks), max(marks), min(marks) from students group by department;
select city, count(*), avg(marks), max(marks) from students group by city;
select department, sum(marks), count(*), avg(marks), max(marks), min(marks) from students group by department;
select department, max(marks) - min(marks) from students group by department;
select department, avg(marks) from students where department='CSE' group by department;
select department, count(*) from students where marks >80 group by department;
select department, avg(marks) from students where marks>=75 group by department;
select city, avg(marks) as Average from students where marks>=70 group by city;
select department, avg(marks) as Average from students where department in ('CSE','ECE') group by department;
select department, count(*) from students group by department having count(*)>2;
select department, sum(marks) from students group by department having sum(marks)>200;
select city, count(*) from students group by city having count(*)>1;
select department, count(*) from students where marks>=80 group by department having count(*)>1;