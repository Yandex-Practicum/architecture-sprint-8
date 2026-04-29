-- CDC: пользователь БД CRM с правом репликации (Debezium создаёт publication и слот).
ALTER USER crm_user WITH REPLICATION;
