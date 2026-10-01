create database library_db;
use library_db;
create table books(
book_id int primary key,
title varchar(100) not null,
isbn varchar(20) unique,
published_year int check (published_year<2027)
);
describe books;
insert into books(book_id, title, isbn, published_year) values
(1,'The Great Gatsby','9780743273565',1925),
(2,'To Kill a Mockingbird','9780061120084','1960'),
(3,'1984','9780451524935',1949);
select * from books;
create table members(
member_id int primary key,
full_name varchar(100),
email varchar(100) unique
);
describe members;
insert into members(member_id, full_name, email) values
(101,'John smith', 'john.smith@email.com'),
(102,'Emma Wilson','emma@email.com'),
(103,'Michael Brown','michael@email.com');
select * from members;
create table loans(
loan_id int primary key,
member_id int,
book_id int,
loan_date date,
foreign key (member_id) references members(member_id),
foreign key (book_id) references books(book_id)
);
describe loans;
INSERT INTO Loans (loan_id, member_id, book_id, loan_date) VALUES
(1, 101, 1, '2025-01-05'), (2, 102, 2, '2025-01-08'),
(3, 103, 3, '2025-01-10'), (4, 101, 2, '2025-02-01'),
(5, 102, 1, '2025-02-05'), (6, 103, 2, '2025-02-12'),
(7, 101, 3, '2025-03-01'), (8, 102, 3, '2025-03-07'),
(9, 103, 1, '2025-03-15'), (10, 101, 1, '2025-04-01');
select * from loans;
select m.full_name as member_name, b.title as book_title from loans l inner join members m on l.member_id=m.member_id inner join books b on l.book_id = b.book_id;
select published_year, count(book_id) as total_books from books group by published_year order by published_year;
create table donation_history(
donation_id int primary key,
book_id int,
donor_name varchar(100),
donation_date date,
foreign key(book_id) references books(book_id)
);
start transaction;
insert into books(book_id, title, isbn, published_year) values
(4,'Animal Farm','9780451526342',1945);
insert into donation_history(donation_id, book_id, donor_name, donation_date)
values(1,4,'raj kumar',curdate());
commit;
create index idx_books_isbn on books(isbn);
select *from books where isbn='9780451524935';