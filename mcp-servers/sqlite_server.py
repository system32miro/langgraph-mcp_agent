import sqlite3
import argparse
from typing import List, Dict, Any, Union
from mcp.server.fastmcp import FastMCP
import os

# --- Funções Auxiliares DB ---

def _get_db_connection(db_path: str) -> sqlite3.Connection:
    """Estabelece conexão com a base de dados SQLite."""
    try:
        conn = sqlite3.connect(db_path)
        # Retorna linhas como dicionários
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Erro ao conectar a DB {db_path}: {e}")
        raise # Re-levanta a excepção para ser capturada pela ferramenta

def _execute_query(db_path: str, query: str, params=(), fetch_all=False) -> Union[List[Dict[str, Any]], int, None]:
    """Executa uma query e fecha a conexão."""
    conn = None
    try:
        conn = _get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetch_all:
            rows = cursor.fetchall()
            # Converte sqlite3.Row para dicionários
            return [dict(row) for row in rows]
        else:
            # Para INSERT, UPDATE, DELETE, commit e retorna linhas afetadas
            conn.commit()
            return cursor.rowcount
    except sqlite3.Error as e:
        print(f"Erro DB ao executar query '{query[:50]}...': {e}")
        # Retorna o erro como string para o agente
        raise ValueError(f"Erro SQLite: {e}")
    finally:
        if conn:
            conn.close()

# --- Servidor MCP ---

mcp = FastMCP("SQLiteDB") # Nome do servidor

# Obtém o caminho da DB a partir dos argumentos ou usa um default
parser = argparse.ArgumentParser()
parser.add_argument("--db-path", default="local_test.db", help="Caminho para o ficheiro da base de dados SQLite.")
# Nota: O FastMCP/MCP pode ter a sua própria forma de lidar com args,
# mas vamos ler aqui para passar para as funções.
# Idealmente, o estado do servidor manteria o db_path.
# Por simplicidade aqui, vamos ler uma vez.
cli_args, _ = parser.parse_known_args()
DB_PATH = os.path.abspath(cli_args.db_path) # Usar caminho absoluto
print(f"--- [SQLite Server] Usando DB em: {DB_PATH} ---")
# Cria o ficheiro DB se não existir (e o diretório)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
# Touch para criar se não existir (ou pode ser criado na primeira conexão)
with open(DB_PATH, 'a'): os.utime(DB_PATH, None)

# --- Ferramentas MCP ---

@mcp.tool()
def list_tables() -> Union[List[str], str]:
    """Lista todas as tabelas na base de dados SQLite."""
    print("--- [SQLite Server] Executando list_tables ---")
    try:
        tables = _execute_query(DB_PATH, "SELECT name FROM sqlite_master WHERE type='table';", fetch_all=True)
        return [table['name'] for table in tables if table['name'] != 'sqlite_sequence']
    except Exception as e:
        return f"Erro ao listar tabelas: {e}"

@mcp.tool()
def describe_table(table_name: str) -> Union[List[Dict[str, Any]], str]:
    """Descreve as colunas de uma tabela específica."""
    print(f"--- [SQLite Server] Executando describe_table para '{table_name}' ---")
    # Validar nome da tabela minimamente para evitar injeção no PRAGMA
    if not table_name.isalnum():
        return "Erro: Nome da tabela inválido."
    try:
        # Usar PRAGMA é seguro aqui pois validamos table_name
        schema = _execute_query(DB_PATH, f"PRAGMA table_info({table_name});", fetch_all=True)
        if not schema:
             return f"Erro: Tabela '{table_name}' não encontrada ou vazia."
        return schema # Retorna a lista de dicionários como recebida
    except Exception as e:
        return f"Erro ao descrever tabela '{table_name}': {e}"

@mcp.tool()
def read_query(query: str) -> Union[List[Dict[str, Any]], str]:
    """Executa uma query SELECT na base de dados SQLite. Cuidado com queries complexas."""
    print(f"--- [SQLite Server] Executando read_query: {query[:100]}... ---")
    # Validação muito básica - permitir apenas SELECT
    if not query.strip().upper().startswith("SELECT"):
        return "Erro: Apenas queries SELECT são permitidas em read_query."
    try:
        results = _execute_query(DB_PATH, query, fetch_all=True)
        return results
    except Exception as e:
        return f"Erro ao executar read_query: {e}"

@mcp.tool()
def write_query(query: str) -> Union[Dict[str, int], str]:
    """Executa uma query INSERT, UPDATE ou DELETE na base de dados SQLite. USAR COM EXTREMO CUIDADO!"""
    print(f"--- [SQLite Server] Executando write_query: {query[:100]}... ---")
    query_upper = query.strip().upper()
    # Validação básica - permitir apenas INSERT, UPDATE, DELETE
    if not (query_upper.startswith("INSERT") or query_upper.startswith("UPDATE") or query_upper.startswith("DELETE")):
        return "Erro: Apenas queries INSERT, UPDATE ou DELETE são permitidas em write_query."
    try:
        affected_rows = _execute_query(DB_PATH, query, fetch_all=False)
        return {"affected_rows": affected_rows if affected_rows is not None else 0}
    except Exception as e:
        return f"Erro ao executar write_query: {e}"

# --- Iniciar Servidor ---
if __name__ == "__main__":
    print(f"--- [SQLite Server] Iniciando com transporte stdio e DB em {DB_PATH}... ---")
    # Passar argumentos relevantes para mcp.run se a biblioteca suportar,
    # caso contrário, eles já foram lidos acima.
    mcp.run(transport="stdio")
