create database pd_db;
use pd_db;
CREATE TABLE physician (
    employeeid INT PRIMARY KEY,
    name VARCHAR(100),
    position VARCHAR(100),
    ssn VARCHAR(20)
);
describe physician;
INSERT INTO physician VALUES
(1,'John Dorian','Staff Internist','111111111'),
(2,'Elliot Reid','Attending Physician','222222222'),
(3,'Christopher Turk','Surgical Attending Physician','333333333'),
(4,'Percival Cox','Senior Attending Physician','444444444'),
(5,'Bob Kelso','Head Chief of Medicine','555555555'),
(6,'Todd Quinlan','Surgical Attending Physician','666666666'),
(7,'John Wen','Surgical Attending Physician','777777777'),
(8,'Keith Dudemeister','MD Resident','888888888'),
(9,'Molly Clock','Attending Psychiatrist','999999999');
select * from physician;
CREATE TABLE department (
    departmentid INT PRIMARY KEY,
    name VARCHAR(100),
    head INT
);
describe department;
INSERT INTO department VALUES
(1,'General Medicine',4),
(2,'Surgery',7),
(3,'Psychiatry',9);
select * from department;
select d.name as department, p.name as head_physician from department d inner join physician p on d.head= p.employeeid;
select * from physician where position='Surgical Attending Physician';
select * from physician where name like 'John%';
select count(*) as total_physicians from physician;
select count(distinct position) from physician;
select position, count(*) as total_employees from physician group by position;
select position, count(*) as total_employees from physician group by position having count(*) >1;
select * from physician order by name asc;
select * from physician order by employeeid desc;
SELECT *FROM physician WHERE employeeid IN (SELECT head FROM department);
select position, count(*) as total_employees from physician group by position order by total_employees desc;
select * from physician where position like 'Attending%';
SELECT * FROM physician WHERE employeeid NOT IN ( SELECT head FROM department);