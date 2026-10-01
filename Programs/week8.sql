DROP DATABASE IF EXISTS Bank_ACID_DB;
CREATE DATABASE Bank_ACID_DB;
USE Bank_ACID_DB;

CREATE TABLE Customer (
    Customer_ID INT PRIMARY KEY,
    Customer_Name VARCHAR(100) NOT NULL,
    Phone VARCHAR(15),
    City VARCHAR(50)
);

CREATE TABLE Account (
    Account_No INT PRIMARY KEY,
    Customer_ID INT,
    Account_Type VARCHAR(20),
    Balance DECIMAL(12,2),
    Branch VARCHAR(50),
    FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID)
);

CREATE TABLE Bank_Transaction (
    Transaction_ID INT PRIMARY KEY AUTO_INCREMENT,
    Account_No INT,
    Transaction_Type VARCHAR(20),
    Amount DECIMAL(12,2),
    Transaction_Date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (Account_No) REFERENCES Account(Account_No)
);

INSERT INTO Customer VALUES
(101,'Ravi Kumar','9876543210','Hyderabad'),
(102,'Priya Sharma','9876543211','Vijayawada'),
(103,'Arjun Reddy','9876543212','Bangalore'),
(104,'Sneha Rao','9876543213','Chennai'),
(105,'Kiran Kumar','9876543214','Hyderabad');

INSERT INTO Account VALUES
(10001,101,'Savings',50000,'Hyderabad'),
(10002,102,'Savings',75000,'Vijayawada'),
(10003,103,'Current',120000,'Bangalore'),
(10004,104,'Savings',45000,'Chennai'),
(10005,105,'Current',90000,'Hyderabad');

INSERT INTO Bank_Transaction
(Account_No,Transaction_Type,Amount)
VALUES
(10001,'DEPOSIT',10000),
(10002,'DEPOSIT',15000),
(10003,'WITHDRAW',20000),
(10004,'DEPOSIT',5000),
(10005,'WITHDRAW',10000);

SELECT * FROM Customer;
SELECT * FROM Account;
SELECT * FROM Bank_Transaction;

-- COMMIT

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

SELECT * FROM Account WHERE Account_No = 10001;

COMMIT;

SELECT * FROM Account WHERE Account_No = 10001;

-- ROLLBACK

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

SELECT * FROM Account WHERE Account_No = 10001;

ROLLBACK;

SELECT * FROM Account WHERE Account_No = 10001;

-- SAVEPOINT

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

SAVEPOINT Deposit1;

UPDATE Account
SET Balance = Balance - 3000
WHERE Account_No = 10002;

SAVEPOINT Withdrawal1;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10003;

ROLLBACK TO SAVEPOINT Withdrawal1;

COMMIT;

SELECT * FROM Account;

-- BANK TRANSFER

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10002;

SELECT *
FROM Account
WHERE Account_No IN (10001,10002);

COMMIT;

SELECT Account_No,Balance
FROM Account
WHERE Account_No IN (10001,10002);

-- TRANSFER WITH ROLLBACK

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 20000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 20000
WHERE Account_No = 10002;

ROLLBACK;

SELECT *
FROM Account
WHERE Account_No IN (10001,10002);

-- ATOMICITY

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10002;

COMMIT;

-- CONSISTENCY

SELECT SUM(Balance) AS Total_Balance
FROM Account;

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10002;

COMMIT;

SELECT SUM(Balance) AS Total_Balance
FROM Account;

-- DURABILITY

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

COMMIT;

SELECT *
FROM Account
WHERE Account_No = 10001;

-- CURRENT ISOLATION LEVEL

SELECT @@SESSION.transaction_isolation;
SELECT @@GLOBAL.transaction_isolation;

-- READ UNCOMMITTED

SET SESSION TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

START TRANSACTION;

SELECT *
FROM Account
WHERE Account_No = 10001;

COMMIT;

-- READ COMMITTED

SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED;

START TRANSACTION;

SELECT *
FROM Account
WHERE Account_No = 10001;

COMMIT;

-- REPEATABLE READ

SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ;

START TRANSACTION;

SELECT *
FROM Account
WHERE Account_No = 10001;

SELECT *
FROM Account
WHERE Account_No = 10001;

COMMIT;

-- SERIALIZABLE

SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;

START TRANSACTION;

SELECT *
FROM Account
WHERE Account_No = 10001;

COMMIT;

-- DEPOSIT

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

COMMIT;

-- WITHDRAWAL

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 5000
WHERE Account_No = 10001;

COMMIT;

-- CANCEL WITHDRAWAL

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

ROLLBACK;

-- TRANSFER WITH SAVEPOINT

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

SAVEPOINT AfterDebit;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10002;

COMMIT;

-- PRACTICE 1

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

COMMIT;

-- PRACTICE 2

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 3000
WHERE Account_No = 10002;

COMMIT;

-- PRACTICE 3

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

ROLLBACK;

-- PRACTICE 4

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 15000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 15000
WHERE Account_No = 10002;

COMMIT;

-- PRACTICE 5

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 20000
WHERE Account_No = 10001;

SAVEPOINT Sender_Debited;

UPDATE Account
SET Balance = Balance + 20000
WHERE Account_No = 10003;

COMMIT;

-- PRACTICE 6

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

SAVEPOINT First_Update;

UPDATE Account
SET Balance = Balance + 3000
WHERE Account_No = 10002;

SAVEPOINT Second_Update;

UPDATE Account
SET Balance = Balance + 7000
WHERE Account_No = 10003;

ROLLBACK TO SAVEPOINT Second_Update;

COMMIT;

-- PRACTICE 7

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 10002;

COMMIT;

-- PRACTICE 8

SELECT SUM(Balance) AS Before_Transfer
FROM Account;

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 15000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 15000
WHERE Account_No = 10002;

COMMIT;

SELECT SUM(Balance) AS After_Transfer
FROM Account;

-- PRACTICE 9

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

COMMIT;

SELECT *
FROM Account
WHERE Account_No = 10001;

-- PRACTICE 16 - INVALID RECEIVER

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 10000
WHERE Account_No = 10001;

UPDATE Account
SET Balance = Balance + 10000
WHERE Account_No = 99999;

ROLLBACK;

-- PRACTICE 17 - INSUFFICIENT BALANCE

START TRANSACTION;

UPDATE Account
SET Balance = Balance - 1000000
WHERE Account_No = 10001
AND Balance >= 1000000;

COMMIT;

-- PRACTICE 18 - SAVEPOINT

START TRANSACTION;

UPDATE Account
SET Balance = Balance + 5000
WHERE Account_No = 10001;

SAVEPOINT Deposit5000;

UPDATE Account
SET Balance = Balance - 2000
WHERE Account_No = 10002;

ROLLBACK TO SAVEPOINT Deposit5000;

COMMIT;

-- FINAL CHECK

SELECT * FROM Customer;
SELECT * FROM Account;
SELECT * FROM Bank_Transaction;

SELECT @@SESSION.transaction_isolation;