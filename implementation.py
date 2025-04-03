import builtins
import contextlib
import io
import os
import asyncio
import sys
import json
from typing import TypedDict, Sequence, Literal, Any, List, Dict

# Langchain/LangGraph Imports
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate # Para prompts mais estruturados
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field # Para definir schemas de args
from langgraph.graph import StateGraph

# Adapters e LLM
try:
    from langchain_mcp_adapters.client import MultiServerMCPClient
except ImportError:
    print("ERRO CRÍTICO: Biblioteca 'langchain_mcp_adapters' não encontrada.")
    sys.exit(1)
from langchain_anthropic import ChatAnthropic

# Stub
from stub import CustomAgent

# --- CONFIGURAÇÃO LLM ---
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("ERRO CRÍTICO: Chave API Anthropic não encontrada. Defina a variável de ambiente 'ANTHROPIC_API_KEY' ou adicione ao .env.")
    sys.exit(1) # Sair se não houver chave

llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=0.1, api_key=api_key) # Temp baixa para mais determinismo
print("Modelo Anthropic Claude carregado.")

# --- ESTADO DO AGENTE ---
class AgentState(TypedDict):
    messages: Sequence[BaseMessage]
    task_description: str
    retrieved_tool_names: List[str] | None
    agent_outcome: Any | None
    mcp_client: MultiServerMCPClient | None
    mcp_tools: Dict[str, BaseTool] | None

# --- LÓGICA DOS NÓS (Integrando LLM) ---

# Função auxiliar para normalização de texto simples
def normalize_text(text: str) -> str:
    """Converte para minúsculas e remove acentos comuns."""
    text = text.lower()
    replacements = {
        'á': 'a', 'à': 'a', 'â': 'a', 'ã': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ü': 'u',
        'ç': 'c'
    }
    for accented, unaccented in replacements.items():
        text = text.replace(accented, unaccented)
    return text

# Recuperador Mock (BigTool Simulado) - COM NORMALIZAÇÃO
def simplified_retrieve_tools(query: str, available_tool_names: List[str]) -> List[str]:
    print(f"\n--- [MOCK BIGTOOL] Retrieving tools for query: '{query}' ---")
    print(f"--- [MOCK BIGTOOL] Available MCP tool names: {available_tool_names} ---")
    normalized_query = normalize_text(query) # Normalizar query
    relevant_names = []
    # Dicionário de palavras-chave para ferramentas
    keyword_map = {
        "tempo": "get_weather", "weather": "get_weather", "clima": "get_weather",
        "soma": "add", "add": "add", "+": "add", "matematica": "add",
        "multiplica": "multiply", "*": "multiply",
        "tabela": "list_tables", "listar tabelas": "list_tables", "tables": "list_tables",
        "colunas": "describe_table", "descrever": "describe_table", "schema": "describe_table",
        "ler": "read_query", "le": "read_query", # Adicionado 'le' para capturar 'lê'
        "select": "read_query", "consultar": "read_query", "query": "read_query",
        "escrever": "write_query", "inserir": "write_query", "atualizar": "write_query", "apagar": "write_query",
        "insert": "write_query", "update": "write_query", "delete": "write_query",
        "base de dados": "list_tables", "database": "list_tables", "db": "list_tables", "sqlite":"list_tables"
    }
    
    # Normalizar todas as chaves do dicionário
    normalized_keyword_map = {normalize_text(k): v for k, v in keyword_map.items()}
    
    # Ordenar keywords por comprimento descendente para evitar correspondências parciais
    sorted_keywords = sorted(normalized_keyword_map.keys(), key=len, reverse=True)

    # Encontrar correspondências de palavras-chave na query normalizada
    for keyword in sorted_keywords:
        if keyword in normalized_query:
            tool_name = normalized_keyword_map[keyword]
            if tool_name in available_tool_names and tool_name not in relevant_names:
                relevant_names.append(tool_name)
    
    # Lógica adicional para read_query (mantida)
    if "read_query" in relevant_names:
         if "describe_table" in available_tool_names and "describe_table" not in relevant_names:
             relevant_names.append("describe_table")
         if "list_tables" in available_tool_names and "list_tables" not in relevant_names:
             relevant_names.append("list_tables")
    
    print(f"--- [MOCK BIGTOOL] Normalized query: '{normalized_query}' ---")
    print(f"--- [MOCK BIGTOOL] Found relevant tool names: {relevant_names} ---")
    return relevant_names

# Roteador (Síncrono) - Mantém-se como antes por simplicidade, mas podia usar LLM
def route_to_agent(state: AgentState) -> Literal["react_agent", "codeact_agent"]:
    # ... (código como antes) ...
    print("\n--- [SUPERVISOR CONDITION] Deciding route ---")
    task_desc = state.get("task_description", "").lower()
    retrieved_tools = state.get("retrieved_tool_names", [])
    print(f"Supervisor analyzing task: '{task_desc}', Tools: {retrieved_tools}")
    complex_keywords = ["calcular", "processar", "combinar", "código", "code", " e ", "sql"] # Adicionado 'sql', 'e'
    if any(keyword in task_desc for keyword in complex_keywords) or len(retrieved_tools or []) > 1:
        print("Supervisor decided: Route to codeact_agent")
        return "codeact_agent"
    else:
        print("Supervisor decided: Route to react_agent")
        return "react_agent"

# Nó Supervisor (Async) - Como antes
async def supervisor(state: AgentState) -> dict:
    # ... (código como antes) ...
    print("\n--- [NODE] Executing supervisor ---")
    last_message = state["messages"][-1]
    task_desc = last_message.content
    mcp_tools = state.get("mcp_tools", {})
    available_tool_names = list(mcp_tools.keys()) if mcp_tools else []
    print(f"Supervisor received task: '{task_desc}'")
    retrieved_tool_names = simplified_retrieve_tools(task_desc, available_tool_names)
    return {
        "task_description": task_desc,
        "retrieved_tool_names": retrieved_tool_names
    }

# Nó ReAct (Async) - CORREÇÃO na formatação do schema
async def react_agent(state: AgentState) -> dict:
    print("\n--- [NODE] Executing react_agent ---")
    task_desc = state["task_description"]
    tool_names = state.get("retrieved_tool_names", [])
    messages = list(state["messages"])
    mcp_tools = state.get("mcp_tools", {})
    agent_outcome = "Não foi possível executar a ação ReAct."

    if not mcp_tools or not llm:
         agent_outcome = "Erro fatal: Ferramentas MCP ou LLM não disponíveis no estado."
         messages.append(AIMessage(content=agent_outcome))
         return {"messages": messages, "agent_outcome": agent_outcome}

    if tool_names:
        tool_name_to_call = tool_names[0]
        if tool_name_to_call not in mcp_tools:
            agent_outcome = f"Erro: Ferramenta recuperada '{tool_name_to_call}' não encontrada."
            messages.append(AIMessage(content=agent_outcome))
            return {"messages": messages, "agent_outcome": agent_outcome}

        tool_to_call: BaseTool = mcp_tools[tool_name_to_call]
        print(f"React Agent will use tool: {tool_to_call.name} - {tool_to_call.description}")

        # ---- CORREÇÃO: Formatar schema para o prompt + ESCAPAR CHAVES ----
        raw_schema_str = 'Nenhum argumento necessário'
        if tool_to_call.args_schema:
            # Se for um dict (schema JSON), converter para string JSON
            if isinstance(tool_to_call.args_schema, dict):
                try:
                    raw_schema_str = json.dumps(tool_to_call.args_schema)
                except TypeError:
                    raw_schema_str = str(tool_to_call.args_schema) # Fallback
            # Se tiver o método schema_json (Pydantic), usar (compatibilidade futura)
            elif hasattr(tool_to_call.args_schema, 'schema_json'):
                 raw_schema_str = tool_to_call.args_schema.schema_json()
            # Senão, usar representação string
            else:
                 raw_schema_str = str(tool_to_call.args_schema)

        # Escapar chaves para o formatador de prompt
        schema_str = raw_schema_str.replace('{', '{{').replace('}', '}}')

        prompt = ChatPromptTemplate.from_messages([
            ("system", f"És um assistente prestável. A tua tarefa é usar a ferramenta '{tool_to_call.name}' para responder ao pedido do utilizador. "
                       f"Descrição da ferramenta: {tool_to_call.description}. Schema de argumentos JSON: {schema_str}. " # Schema escapado aqui
                       f"Analisa a conversa e invoca a ferramenta com os argumentos corretos."),
            *messages
        ])
        # ----------------------------------------------

        llm_with_specific_tool = llm.bind_tools([tool_to_call], tool_choice=tool_to_call.name)
        print(f"React Agent: Chamando LLM para obter args para {tool_to_call.name}...")

        try:
            # Agora deve formatar corretamente
            ai_message_with_tool_call = await llm_with_specific_tool.ainvoke(prompt.format_messages())
            messages.append(ai_message_with_tool_call)

            if not ai_message_with_tool_call.tool_calls:
                print("React Agent: LLM não gerou uma chamada de ferramenta.")
                agent_outcome = ai_message_with_tool_call.content
                return {"messages": messages, "agent_outcome": agent_outcome}

            tool_call_info = ai_message_with_tool_call.tool_calls[0]
            args = tool_call_info.get('args', {})
            call_id = tool_call_info.get('id', tool_name_to_call)

            print(f"React Agent: LLM gerou chamada para {tool_name_to_call} com args: {args}")

            try:
                tool_result = await tool_to_call.ainvoke(args)
                agent_outcome = str(tool_result)
                messages.append(ToolMessage(content=agent_outcome, tool_call_id=call_id))
            except Exception as e:
                agent_outcome = f"Erro ao invocar a ferramenta MCP {tool_to_call.name} com args {args}: {e}"
                messages.append(ToolMessage(content=agent_outcome, tool_call_id=call_id))
                import traceback; print(traceback.format_exc())

        except Exception as e:
             agent_outcome = f"Erro ao chamar LLM para obter argumentos para {tool_to_call.name}: {e}"
             messages.append(AIMessage(content=agent_outcome))
             import traceback; print(traceback.format_exc()) # Imprimir traceback completo

    else:
        print("React Agent: Nenhuma ferramenta relevante encontrada pelo BigTool mock.")
        try:
             prompt = ChatPromptTemplate.from_messages([
                 ("system", "És um assistente prestável. Responde diretamente ao utilizador."),
                 *messages
             ])
             direct_response = await llm.ainvoke(prompt.format_messages())
             agent_outcome = direct_response.content
             messages.append(direct_response)
        except Exception as e:
            agent_outcome = f"Erro ao tentar obter resposta direta do LLM: {e}"
            messages.append(AIMessage(content=agent_outcome))


    print(f"React Agent final outcome: {agent_outcome}")
    return {"messages": messages, "agent_outcome": agent_outcome}


# Eval inseguro (Suporte a código sync e async) - AGORA ASYNC
async def unsafe_eval_for_test(code: str, _locals: dict) -> tuple[str, dict]:
    """
    Executa código Python potencialmente assíncrono em um ambiente de teste.
    AVISO: Esta função é APENAS para testes e não deve ser utilizada em produção.

    Args:
        code: String contendo código Python a ser executado
        _locals: Dicionário com variáveis locais (incluindo ferramentas) a serem disponibilizadas para o código

    Returns:
        Tuple contendo (output do stdout, novas variáveis criadas)
    """
    print("\n!!! WARNING: Using unsafe eval for testing !!!")
    original_keys = set(_locals.keys())
    result_str = ""

    # Usar o dicionário _locals diretamente como namespace global/local para exec
    exec_namespace = {
        "__builtins__": builtins,
        "asyncio": asyncio,
    }
    exec_namespace.update(_locals)

    # Verificar se o código contém definições assíncronas
    is_async_code = "async def main():" in code # Ser mais específico

    print(f"--- [UNSAFE EVAL] Executando {'código assíncrono' if is_async_code else 'código síncrono'}:\n---\n{code}\n---")

    try:
        # Redireccionar stdout para capturar a saída
        with contextlib.redirect_stdout(io.StringIO()) as f:
            if is_async_code:
                # Executar o código para definir funções e variáveis no namespace
                exec(code, exec_namespace)

                # Verificar se main() existe e é assíncrona
                main_func = exec_namespace.get("main")
                if main_func and asyncio.iscoroutinefunction(main_func):
                    # ---- CORREÇÃO: Chamar await diretamente ----
                    print("--- [UNSAFE EVAL] Awaiting generated main() coroutine...")
                    await main_func()
                    # -----------------------------------------
                else:
                     print("--- [UNSAFE EVAL] Warning: Código async detectado, mas função 'async def main()' não encontrada ou não é corrotina.")
            else:
                # Execução síncrona
                exec(code, exec_namespace)

        # Capturar stdout
        result_str = f.getvalue().strip()
        if not result_str:
            result_str = f"<{'código assíncrono' if is_async_code else 'código síncrono'} executado, sem output no stdout>"

    except Exception as e:
        result_str = f"Erro durante a execução: {repr(e)}"
        import traceback; print(traceback.format_exc())

    # Coletar novas variáveis criadas durante a execução
    new_vars = {k: v for k, v in exec_namespace.items()
                if k not in ['__builtins__', 'asyncio'] and k not in original_keys
                and not k.startswith('_')}

    # Procurar por 'final_output' no namespace modificado
    if "final_output" in exec_namespace:
         # Atualizar new_vars se final_output foi modificado ou criado
         new_vars["final_output"] = exec_namespace["final_output"]
    elif "final_output" not in new_vars:
         # Procurar outros nomes se 'final_output' não foi definido explicitamente
         for result_var in ["resultado", "resultado_final", "resposta_final", "resposta"]:
             if result_var in exec_namespace and exec_namespace[result_var] is not None:
                 new_vars["final_output"] = exec_namespace[result_var]
                 break

    print(f"--- [UNSAFE EVAL] Result stdout: '{result_str}' ---")
    print(f"--- [UNSAFE EVAL] New/Updated variables (repr): {{k: repr(v) for k, v in new_vars.items()}} ---")
    return result_str, new_vars


# Nó CodeAct (Async) - CORREÇÃO no prompt system
async def codeact_agent(state: AgentState) -> dict:
    print("\n--- [NODE] Executing codeact_agent ---")
    task_desc = state["task_description"]
    tool_names = state.get("retrieved_tool_names", [])
    messages = list(state["messages"])
    mcp_tools = state.get("mcp_tools", {})
    agent_outcome = "Falha ao executar lógica CodeAct."

    if not mcp_tools or not llm:
         return {"messages": list(state["messages"]), "agent_outcome": "Erro fatal: Ferramentas MCP ou LLM não disponíveis."}
    if not tool_names:
         return {"messages": list(state["messages"]), "agent_outcome": "Nenhuma ferramenta relevante encontrada."}

    available_tools_for_eval = {}
    tool_descriptions_for_prompt = []
    print("CodeAct Agent: Preparing MCP tools for LLM and eval:")
    for tool_name in tool_names:
        if tool_name in mcp_tools:
             tool: BaseTool = mcp_tools[tool_name]
             available_tools_for_eval[tool_name] = tool
             # ---- CORREÇÃO: Formatar descrição dos args + ESCAPAR CHAVES ----
             arg_keys_str = ''
             if tool.args_schema:
                 # Se for dict com 'properties', extrair as chaves
                 if isinstance(tool.args_schema, dict) and 'properties' in tool.args_schema and isinstance(tool.args_schema['properties'], dict):
                      arg_keys_str = ", ".join(tool.args_schema['properties'].keys())
                 # Se for Pydantic model (v1 ou v2), tentar extrair de .schema()
                 elif hasattr(tool.args_schema, 'schema') and callable(tool.args_schema.schema):
                     try:
                         schema_dict = tool.args_schema.schema()
                         if isinstance(schema_dict, dict) and 'properties' in schema_dict and isinstance(schema_dict['properties'], dict):
                              arg_keys_str = ", ".join(schema_dict['properties'].keys())
                     except Exception: # Captura erros ao chamar .schema()
                          pass # Mantém arg_keys_str vazio se falhar
                 # Fallback para string se não for reconhecido
                 if not arg_keys_str:
                     arg_keys_str = str(tool.args_schema)

             # Escapar chaves na string de argumentos e descrição para o formatador
             escaped_arg_keys_str = arg_keys_str.replace('{', '{{').replace('}', '}}')
             escaped_description = tool.description.replace('{', '{{').replace('}', '}}')

             desc = f"- {tool.name}({escaped_arg_keys_str}): {escaped_description}"
             # ------------------------------------------
             tool_descriptions_for_prompt.append(desc)
             print(f"  - {tool_name}")
        else:
            print(f"  - AVISO: Tool name '{tool_name}' recuperado mas não encontrado.")

    if not available_tools_for_eval:
         return {"messages": list(state["messages"]), "agent_outcome": "Nenhuma ferramenta válida encontrada após recuperação."}

    # ---- CHAMADA LLM para gerar código Python ----
    tools_prompt_section = "\n".join(tool_descriptions_for_prompt)
    system_prompt = f"""És um assistente de programação Python especializado em código assíncrono. A tua tarefa é escrever um script Python assíncrono para realizar o pedido do utilizador.
Usa APENAS estas ferramentas disponíveis:
{tools_prompt_section}

IMPORTANTE:
1. O teu código deve estar contido numa função assíncrona `main()`.
2. Todas as ferramentas são assíncronas. Deves chamá-las usando `await tool_name.ainvoke(arguments)`.
3. O argumento `arguments` para `ainvoke` DEVE ser sempre um **DICIONÁRIO** Python contendo os parâmetros necessários para a ferramenta, mesmo que haja apenas um parâmetro.
4. Usa `print()` para mostrar resultados intermédios se necessário.
5. Define o resultado final numa variável global chamada `final_output`.
6. NÃO precisas adicionar `import asyncio; asyncio.run(main())` no final.

Exemplo 1 (Ferramenta com um argumento):
```python
async def main():
    global final_output
    try:
        resultado_weather = await get_weather.ainvoke({{"location": "Lisboa"}}) # Argumento como dicionário
        print("Tempo:", resultado_weather)
        final_output = f"O tempo em Lisboa é: {{resultado_weather}}"
    except Exception as e:
        print("Erro no Exemplo 1:", e)
        final_output = f"Erro ao obter tempo: {{e}}"
```

Exemplo 2 (Ferramenta com múltiplos argumentos):
```python
async def main():
    global final_output
    try:
        resultado_soma = await add.ainvoke({{"a": 5, "b": 3}}) # Argumentos como dicionário
        print("Soma:", resultado_soma)
        final_output = f"A soma de 5 e 3 é: {{resultado_soma}}"
    except Exception as e:
        print("Erro no Exemplo 2:", e)
        final_output = f"Erro ao somar: {{e}}"

# Lembra-te: Sempre um dicionário para ainvoke!
```
"""
    # ------------------------------------------------------------
    code_gen_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        *messages # Histórico da conversa - Esta linha pode não ser necessária se construirmos manualmente abaixo
    ])
    print("CodeAct Agent: Chamando LLM para gerar código...")
    try:
        # ---- CORREÇÃO: Construir lista de mensagens manualmente e invocar ----
        # Construir a lista de mensagens a enviar ao LLM
        llm_input_messages = [SystemMessage(content=system_prompt)] + messages

        # Passar a lista diretamente para ainvoke, em vez de format_messages()
        code_gen_response = await llm.ainvoke(llm_input_messages)
        # ---------------------------------------------------------------------

        # O resto da lógica para processar a resposta continua igual...
        # Assumindo que code_gen_response é uma AIMessage ou similar com 'content'
        if hasattr(code_gen_response, 'content'):
             generated_content = code_gen_response.content
             # Adicionar a resposta do LLM ao histórico ANTES de processar/executar
             # É importante manter o histórico completo
             messages.append(code_gen_response)
        else:
             # Fallback se a estrutura for diferente
             generated_content = str(code_gen_response)
             # Adicionar como AIMessage ao histórico
             messages.append(AIMessage(content=generated_content))

        print(f"CodeAct Agent: LLM gerou resposta:\n---\n{generated_content}\n---")

        # Extrair código Python do bloco de markdown, se existir
        generated_code = "" # Inicializar vazio
        is_code_block = False
        if "```python" in generated_content:
            potential_code = generated_content.split("```python")[1].split("```")[0].strip()
            # Heurística para verificar se é código
            if any(kw in potential_code for kw in ['import ', 'async def ', 'def ', 'print(', '=', 'await']) or potential_code.startswith('#'):
                 generated_code = potential_code
                 is_code_block = True
        elif "```" in generated_content:
             # Tentar extrair de um bloco genérico ```
            potential_code = generated_content.split("```")[1].split("```")[0].strip()
            # Heurística mais forte para bloco genérico
            if 'async def main():' in potential_code or 'await' in potential_code or 'import' in potential_code:
                 generated_code = potential_code
                 is_code_block = True


        # Só tentar executar se for detetado código Python no generated_code extraído
        if is_code_block and generated_code:
            print(f"CodeAct Agent: Código extraído para execução:\n---\n{generated_code}\n---")
            # Adicionar lógica para garantir que 'final_output' é acessível globalmente no eval
            exec_globals = {'final_output': None} # Inicializar no escopo que será passado
            exec_globals.update(available_tools_for_eval) # Adicionar ferramentas

            # Modificar unsafe_eval para aceitar e retornar globals, ou adaptar aqui
            # Assumindo que unsafe_eval usa o dict passado como globals/locals
            # NOTA: A implementação atual de unsafe_eval_for_test já tenta encontrar 'final_output'
            # no namespace após a execução. Passar 'exec_globals' como _locals deve funcionar.
            stdout_result, new_vars = await unsafe_eval_for_test(generated_code, exec_globals)

            # Prioriza var 'final_output' capturada do escopo de execução, senão o stdout do print()
            final_output_from_exec = new_vars.get('final_output') # Capturar de new_vars como unsafe_eval faz

            if final_output_from_exec is not None:
                 agent_outcome = final_output_from_exec
            elif stdout_result:
                 agent_outcome = stdout_result
            else: # Se não houver nem var nem print
                 agent_outcome = "<Execução de código concluída sem output explícito>"

        else:
             # Se o LLM não gerou código (ex: pediu clarificação), usar a sua resposta como outcome
             agent_outcome = generated_content
             print("CodeAct Agent: LLM não gerou código executável ou código não foi extraído, usando a resposta como outcome.")


    except Exception as e:
        agent_outcome = f"Erro durante a geração ou execução de código CodeAct: {e}"
        # Adicionar a mensagem de erro ao histórico ANTES de retornar
        # A resposta do LLM já foi adicionada, então só adicionamos uma mensagem de erro se ocorrer exceção DEPOIS
        if not isinstance(messages[-1], AIMessage) or "Erro no CodeAct" not in messages[-1].content:
             messages.append(AIMessage(content=f"Erro no CodeAct após resposta do LLM: {e}"))
        import traceback; print(traceback.format_exc()) # Imprimir traceback completo

    print(f"CodeAct Agent final outcome: {agent_outcome}")
    # Garantir que as mensagens atualizadas (incluindo resposta do LLM e/ou erro) são retornadas
    return {"messages": messages, "agent_outcome": agent_outcome}


# Nó Final (Async) - AGORA USA LLM PARA RESPOSTA FINAL
async def final_answer(state: AgentState) -> dict:
    print("\n--- [NODE] Executing final_answer ---")
    messages = list(state["messages"])
    final_outcome = state.get("agent_outcome", "Não foi possível determinar o resultado final.")
    print(f"Final Answer Node: Recebeu outcome: {final_outcome}")

    # ---- CHAMADA LLM para gerar resposta final ----
    if not isinstance(messages[-1], AIMessage) or messages[-1].tool_calls:
         if llm:
             print("Final Answer: Chamando LLM para gerar resposta final...")
             max_retries = 3
             base_delay = 1.0
             for attempt in range(max_retries):
                 try:
                     # ---- CORREÇÃO: Incorporar instrução no system prompt ----
                     final_system_prompt = """És um assistente prestável e preciso. A tua tarefa é:
1. Confiar completamente nos resultados das ferramentas externas utilizadas ou no código executado - considera esses dados como factos verificados e precisos.
2. Resumir os resultados da interação de forma clara e direta.
3. Responder à questão inicial do utilizador com base na informação recolhida.
4. NUNCA sugerir que não tens informações ou que não podes responder quando os dados foram obtidos pelas ferramentas ou pelo código.
5. Manter a resposta concisa e factual, baseada nos dados recebidos."""
                     # ---------------------------------------------------------

                     final_prompt = ChatPromptTemplate.from_messages([
                         # Usar o prompt do sistema atualizado
                         ("system", final_system_prompt),
                         # Passar apenas as mensagens do histórico, sem adicionar SystemMessage extra
                         *messages
                     ])
                     # Chamar LLM com o histórico correto
                     final_response = await llm.ainvoke(final_prompt.format_messages()) # Passar mensagens formatadas pelo template
                     messages.append(final_response)
                     print(f"Final Answer: Resposta LLM: {final_response.content}")
                     break
                 except Exception as e:
                     # Lógica de retry e tratamento de erro permanece a mesma
                     if "ResourceExhausted" in str(e) or "429" in str(e) or "rate_limit_error" in str(e).lower(): # Adicionado check para Anthropic error type
                         if attempt < max_retries - 1:
                             delay = base_delay * (2 ** attempt)
                             print(f"Rate limit atingido. Tentando novamente em {delay:.2f} segundos...")
                             await asyncio.sleep(delay)
                         else:
                             print("Rate limit atingido. Máximo de tentativas excedido.")
                             messages.append(AIMessage(content=f"Concluído, mas ocorreu um erro de limite de taxa ao formatar a resposta final. Resultado bruto: {final_outcome}"))
                             break # Sair após erro final de rate limit
                     elif "multiple non-consecutive system messages" in str(e): # Capturar erro específico do Claude
                          print(f"Erro de formatação de mensagem do sistema: {e}")
                          messages.append(AIMessage(content=f"Concluído, mas ocorreu um erro ao formatar a mensagem para o LLM. Resultado bruto: {final_outcome}"))
                          # Adicionar mais debug se necessário: print(final_prompt.format_messages())
                          break # Sair do loop de retries para este erro
                     else:
                         print(f"Erro não relacionado a rate limit ao gerar resposta final com LLM: {e}")
                         messages.append(AIMessage(content=f"Concluído, mas ocorreu um erro inesperado ao formatar a resposta final. Resultado bruto: {final_outcome}"))
                         import traceback; print(traceback.format_exc()) # Imprimir traceback para erros inesperados
                         break
         else:
              messages.append(AIMessage(content=f"Concluído. Resultado: {final_outcome}"))
    else:
         print("Final Answer: Última mensagem já é uma resposta AI, não chamando LLM.")

    return {"messages": messages}

# --- Função Principal Async ---
async def main():
    # Verificações e Configuração MCP
    if MultiServerMCPClient is None: 
        print("ERRO CRÍTICO: Biblioteca 'langchain_mcp_adapters' não encontrada.")
        return
    
    if llm is None: 
        print("ERRO CRÍTICO: LLM Anthropic não configurado. Verifique sua chave API no .env.")
        return
    
    # Verificar se LLM está inicializado corretamente com o API_KEY do .env
    try:
        # Teste simples do LLM para confirmar que a API key está funcionando
        resposta_teste = await llm.ainvoke([HumanMessage(content="Olá, estás a funcionar?")])
        print(f"LLM teste de conexão: {resposta_teste.content[:50]}...")
    except Exception as e:
        print(f"ERRO CRÍTICO: Falha ao testar o LLM Anthropic. Verifique sua API key: {e}")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    mcp_servers_dir = os.path.join(script_dir, "mcp-servers")
    math_server_path = os.path.join(mcp_servers_dir, "math_server.py")
    weather_server_path = os.path.join(mcp_servers_dir, "weather_server.py")
    sqlite_server_path = os.path.join(mcp_servers_dir, "sqlite_server.py")
    data_dir = os.path.join(script_dir, "data")
    db_file_path = os.path.join(data_dir, "travel.sqlite")

    if not all(os.path.exists(p) for p in [math_server_path, weather_server_path, sqlite_server_path]):
        print(f"ERRO: Scripts dos servidores MCP não encontrados em {mcp_servers_dir}")
        return
        
    if not os.path.exists(db_file_path):
        # Tentar criar o diretório data se não existir
        os.makedirs(data_dir, exist_ok=True)
        print(f"AVISO: Base de dados não encontrada em {db_file_path}. A execução pode falhar se for necessária.")
        # Poderíamos adicionar lógica para criar um DB vazio aqui se necessário

    mcp_server_config = {
         "math": {"command": sys.executable, "args": [math_server_path], "transport": "stdio"},
         "weather": {"command": sys.executable, "args": [weather_server_path], "transport": "stdio"},
         "sqlite": {"command": sys.executable, "args": [sqlite_server_path, "--db-path", db_file_path], "transport": "stdio"}
    }

    print("A iniciar cliente MCP e servidores locais via stdio...")
    try:
        async with MultiServerMCPClient(mcp_server_config) as mcp_client:
            print("Cliente MCP pronto. A obter ferramentas...")
            try:
                # get_tools() é síncrono
                mcp_tools_list: List[BaseTool] = mcp_client.get_tools()
                mcp_tools_dict = {tool.name: tool for tool in mcp_tools_list}
                print(f"Ferramentas MCP carregadas: {list(mcp_tools_dict.keys())}")
                
                if not mcp_tools_dict:
                    print("ERRO: Nenhuma ferramenta MCP foi carregada.")
                    return
                    
            except Exception as e:
                print(f"ERRO ao obter ferramentas do cliente MCP: {e}")
                return

            # Instanciar o Agente LangGraph
            agent_builder = CustomAgent(
                state_schema=AgentState,
                impl=[
                    ("supervisor", supervisor),
                    ("react_agent", react_agent),
                    ("codeact_agent", codeact_agent),
                    ("final_answer", final_answer),
                    ("conditional_edge_1", route_to_agent),
                ],
            )
            compiled_agent = agent_builder.compile()

            print("\nExecutando testes com LLM Anthropic e ferramentas MCP...")
            base_initial_state = {"mcp_client": mcp_client, "mcp_tools": mcp_tools_dict}

            # Teste 1: ReAct Simples - Consulta de tempo (ReAct)
            print("\n\n===== TESTE 1: PREVISÃO DO TEMPO (ReAct c/ Anthropic) =====")
            initial_state_1 = {**base_initial_state, "messages": [HumanMessage(content="qual é o tempo em lisboa?")]}
            async for step in compiled_agent.astream(initial_state_1): 
                print(f"\nStep Output: {step}")

            # Teste 2: CodeAct - Consulta de tempo + matemática (utiliza múltiplas ferramentas)
            print("\n\n===== TESTE 2: TAREFA MULTI-FERRAMENTA (CodeAct c/ Anthropic) =====")
            initial_state_2 = {**base_initial_state, "messages": [HumanMessage(content="qual é o tempo em porto e calcula a soma de 10 e 5?")]}
            async for step in compiled_agent.astream(initial_state_2): 
                print(f"\nStep Output: {step}")

            # Teste 3: SQL - Listar tabelas
            print("\n\n===== TESTE 3: LISTAR TABELAS SQLITE (ReAct c/ Anthropic) =====")
            initial_state_3 = {**base_initial_state, "messages": [HumanMessage(content="lista as tabelas da base de dados de viagens")]}
            async for step in compiled_agent.astream(initial_state_3): 
                print(f"\nStep Output: {step}")

            print("\nTestes concluídos com sucesso!")

    except Exception as e:
        print(f"\nERRO GERAL DURANTE A EXECUÇÃO: {e}")
        import traceback; print(traceback.format_exc())

# --- Ponto de Entrada ---
if __name__ == "__main__":
    # Adicionar tratamento para SIGINT (Ctrl+C) para fechar cliente MCP graciosamente
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExecução interrompida pelo utilizador.")