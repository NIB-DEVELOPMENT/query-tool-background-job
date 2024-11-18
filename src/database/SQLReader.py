class SQLReader():
    def __init__(self):
        pass
    
    def getSQL(self, scriptPath : str) -> str:
        sql : str = None
        with open(scriptPath,"r") as sqlFile:
            sql = sqlFile.read()
        return sql