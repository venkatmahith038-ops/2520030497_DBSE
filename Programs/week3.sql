
CREATE DATABASE BankDB;
USE BankDB;

-- 1. CREATE CORE TABLES
CREATE TABLE Customer (
    Customer_ID INT PRIMARY KEY,
    Customer_Name VARCHAR(100) NOT NULL,
    Phone VARCHAR(15),
    Email VARCHAR(100),
    City VARCHAR(50)
);

CREATE TABLE Account (
    Account_No INT PRIMARY KEY,
    Customer_ID INT,
    Account_Type VARCHAR(20),
    Balance DECIMAL(12,2) DEFAULT 0,
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

CREATE TABLE Loan (
    Loan_ID INT PRIMARY KEY,
    Customer_ID INT,
    Loan_Type VARCHAR(30),
    Loan_Amount DECIMAL(12,2),
    Interest_Rate DECIMAL(5,2),
    FOREIGN KEY (Customer_ID) REFERENCES Customer(Customer_ID)
);

CREATE TABLE Transaction_Audit (
    Audit_ID INT PRIMARY KEY AUTO_INCREMENT,
    Transaction_ID INT,
    Account_No INT,
    Transaction_Type VARCHAR(20),
    Amount DECIMAL(12,2),
    Audit_Date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Account_Audit (
    Audit_ID INT PRIMARY KEY AUTO_INCREMENT,
    Account_No INT,
    Old_Balance DECIMAL(12,2),
    New_Balance DECIMAL(12,2),
    Changed_Date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. INSERT 10 CUSTOMERS
INSERT INTO Customer (Customer_ID, Customer_Name, Phone, Email, City) VALUES
(101, 'Ravi Kumar', '9876543210', 'ravi@gmail.com', 'Hyderabad'),
(102, 'Priya Sharma', '9876543211', 'priya@gmail.com', 'Vijayawada'),
(103, 'Arjun Reddy', '9876543212', 'arjun@gmail.com', 'Bangalore'),
(104, 'Sneha Rao', '9876543213', 'sneha@gmail.com', 'Chennai'),
(105, 'Kiran Kumar', '9876543214', 'kiran@gmail.com', 'Hyderabad'),
(106, 'Ananya Sen', '9876543215', 'ananya@gmail.com', 'Kolkata'),
(107, 'Vikram Malhotra', '9876543216', 'vikram@gmail.com', 'Mumbai'),
(108, 'Neha Patel', '9876543217', 'neha@gmail.com', 'Ahmedabad'),
(109, 'Suresh Mehta', '9876543218', 'suresh@gmail.com', 'Delhi'),
(110, 'Pooja Verma', '9876543219', 'pooja@gmail.com', 'Pune');

-- 3. INSERT 10 ACCOUNTS
INSERT INTO Account (Account_No, Customer_ID, Account_Type, Balance, Branch) VALUES
(10001, 101, 'Savings', 50000, 'Hyderabad'),
(10002, 102, 'Savings', 75000, 'Vijayawada'),
(10003, 103, 'Current', 120000, 'Bangalore'),
(10004, 104, 'Savings', 45000, 'Chennai'),
(10005, 105, 'Current', 90000, 'Hyderabad'),
(10006, 106, 'Savings', 30000, 'Kolkata'),
(10007, 107, 'Current', 200000, 'Mumbai'),
(10008, 108, 'Savings', 65000, 'Ahmedabad'),
(10009, 109, 'Current', 150000, 'Delhi'),
(10010, 110, 'Savings', 80000, 'Pune');

-- 4. INSERT 20 TRANSACTIONS
INSERT INTO Bank_Transaction (Account_No, Transaction_Type, Amount) VALUES
(10001, 'DEPOSIT', 10000), (10002, 'DEPOSIT', 15000),
(10003, 'WITHDRAW', 20000), (10004, 'DEPOSIT', 5000),
(10005, 'WITHDRAW', 10000), (10006, 'DEPOSIT', 12000),
(10007, 'WITHDRAW', 50000), (10008, 'DEPOSIT', 8000),
(10009, 'WITHDRAW', 25000), (10010, 'DEPOSIT', 10000),
(10001, 'WITHDRAW', 5000),  (10002, 'WITHDRAW', 7000),
(10003, 'DEPOSIT', 30000), (10004, 'WITHDRAW', 2000),
(10005, 'DEPOSIT', 15000), (10006, 'WITHDRAW', 4000),
(10007, 'DEPOSIT', 25000), (10008, 'WITHDRAW', 6000),
(10009, 'DEPOSIT', 40000), (10010, 'WITHDRAW', 12000);

-- 5 & 6. PROCEDURES: DEPOSIT AND WITHDRAWAL
DELIMITER //

CREATE PROCEDURE DepositMoney(IN p_Account_No INT, IN p_Amount DECIMAL(12,2))
BEGIN
    INSERT INTO Bank_Transaction (Account_No, Transaction_Type, Amount)
    VALUES (p_Account_No, 'DEPOSIT', p_Amount);
END //

CREATE PROCEDURE WithdrawMoney(IN p_Account_No INT, IN p_Amount DECIMAL(12,2))
BEGIN
    INSERT INTO Bank_Transaction (Account_No, Transaction_Type, Amount)
    VALUES (p_Account_No, 'WITHDRAW', p_Amount);
END //

-- 7. PROCEDURE: TRANSFER MONEY
CREATE PROCEDURE TransferMoney(
    IN SenderAccount INT, 
    IN ReceiverAccount INT, 
    IN TransferAmount DECIMAL(12,2)
)
BEGIN
    DECLARE v_SenderBalance DECIMAL(12,2);
    
    SELECT Balance INTO v_SenderBalance FROM Account WHERE Account_No = SenderAccount;
    
    IF v_SenderBalance < TransferAmount THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Transfer Failed: Insufficient Balance';
    ELSE
        CALL WithdrawMoney(SenderAccount, TransferAmount);
        CALL DepositMoney(ReceiverAccount, TransferAmount);
    END IF;
END //

-- 8. TRIGGER: INSUFFICIENT BALANCE VALIDATION
CREATE TRIGGER PreventOverdraft
BEFORE INSERT ON Bank_Transaction
FOR EACH ROW
BEGIN
    DECLARE v_Bal DECIMAL(12,2);
    IF NEW.Transaction_Type = 'WITHDRAW' THEN
        SELECT Balance INTO v_Bal FROM Account WHERE Account_No = NEW.Account_No;
        IF NEW.Amount > v_Bal THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Transaction Rejected: Insufficient balance.';
        END IF;
    END IF;
END //

-- 9. TRIGGER: TRANSACTION AUDIT LOG
CREATE TRIGGER LogTransaction
AFTER INSERT ON Bank_Transaction
FOR EACH ROW
BEGIN
    INSERT INTO Transaction_Audit (Transaction_ID, Account_No, Transaction_Type, Amount)
    VALUES (NEW.Transaction_ID, NEW.Account_No, NEW.Transaction_Type, NEW.Amount);
END //

-- 10. TRIGGER: AUTO-UPDATE ACCOUNT BALANCE
CREATE TRIGGER SyncAccountBalance
AFTER INSERT ON Bank_Transaction
FOR EACH ROW
BEGIN
    IF NEW.Transaction_Type = 'DEPOSIT' THEN
        UPDATE Account SET Balance = Balance + NEW.Amount WHERE Account_No = NEW.Account_No;
    ELSEIF NEW.Transaction_Type = 'WITHDRAW' THEN
        UPDATE Account SET Balance = Balance - NEW.Amount WHERE Account_No = NEW.Account_No;
    END IF;
END //

-- 11. TRIGGER: ACCOUNT BALANCE CHANGE AUDIT
CREATE TRIGGER LogAccountBalanceChange
AFTER UPDATE ON Account
FOR EACH ROW
BEGIN
    IF OLD.Balance <> NEW.Balance THEN
        INSERT INTO Account_Audit (Account_No, Old_Balance, New_Balance)
        VALUES (NEW.Account_No, OLD.Balance, NEW.Balance);
    END IF;
END //

DELIMITER ;

-- 12. TEST SUCCESSFUL TRANSACTIONS
CALL DepositMoney(10001, 15000);
CALL TransferMoney(10001, 10002, 5000);

-- 13. TEST FAILED TRANSACTION (Uncomment to test trigger rejection)
-- CALL WithdrawMoney(10001, 9999999); 

-- 14. DISPLAY TRANSACTION HISTORY
SELECT * FROM Bank_Transaction WHERE Account_No = 10001;
SELECT * FROM Transaction_Audit;
SELECT * FROM Account_Audit;

-- 15. DISPLAY CUSTOMER ACCOUNT SUMMARY
SELECT 
    C.Customer_ID, C.Customer_Name, A.Account_No, A.Account_Type, A.Balance, A.Branch
FROM Customer C
JOIN Account A ON C.Customer_ID = A.Customer_ID;