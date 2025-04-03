import os
import aiohttp
import json
from typing import List, Dict, Optional, Union, Any
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Carregar variáveis de ambiente
load_dotenv()

# Configuração da API OpenWeatherMap
API_KEY = os.getenv("OPENWEATHER_API_KEY")
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

mcp = FastMCP("Weather")

@mcp.tool()
async def get_weather(location: str) -> Dict[str, Any]:
    """
    Obtém informações meteorológicas atuais para uma localização específica.
    
    Args:
        location (str): O nome da cidade ou localização (ex: "Lisboa", "Porto", "London")
        
    Returns:
        Informações detalhadas sobre o tempo atual na localização solicitada.
    """
    if not location or not isinstance(location, str):
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": "Erro: A localização deve ser uma string válida."
                }
            ]
        }
    
    try:
        params = {
            "q": location,
            "appid": API_KEY,
            "units": "metric",  # Para temperatura em Celsius
            "lang": "pt"        # Para descrições em português
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Formatar a resposta
                    city_name = data["name"]
                    country = data.get("sys", {}).get("country", "")
                    temp = data["main"]["temp"]
                    feels_like = data["main"]["feels_like"]
                    humidity = data["main"].get("humidity", "N/A")
                    weather_desc = data["weather"][0]["description"]
                    wind_speed = data.get("wind", {}).get("speed", "N/A")
                    
                    formatted_response = {
                        "cidade": city_name,
                        "país": country,
                        "temperatura": f"{temp}°C",
                        "sensação térmica": f"{feels_like}°C",
                        "humidade": f"{humidity}%",
                        "condições": weather_desc,
                        "vento": f"{wind_speed} m/s"
                    }
                    
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Tempo atual em {city_name}, {country}: {temp}°C, {weather_desc}. Sensação térmica de {feels_like}°C, humidade de {humidity}% e vento a {wind_speed} m/s."
                            },
                            {
                                "type": "json",
                                "json": formatted_response
                            }
                        ]
                    }
                elif response.status == 404:
                    return {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"Erro: Localização '{location}' não encontrada. Verifique o nome da cidade e tente novamente."
                            }
                        ]
                    }
                else:
                    error_data = await response.text()
                    return {
                        "isError": True,
                        "content": [
                            {
                                "type": "text",
                                "text": f"Erro ao consultar serviço de meteorologia: {response.status} - {error_data}"
                            }
                        ]
                    }
    except Exception as e:
        return {
            "isError": True,
            "content": [
                {
                    "type": "text",
                    "text": f"Erro ao processar pedido: {str(e)}"
                }
            ]
        }

# Versão simplificada para compatibilidade com implementações antigas
@mcp.tool()
async def get_weather_simple(location: str) -> str:
    """
    Versão simplificada que retorna apenas uma string com o tempo para compatibilidade.
    
    Args:
        location (str): O nome da cidade ou localização
    """
    result = await get_weather(location)
    
    if "isError" in result and result["isError"]:
        return f"Erro ao consultar tempo para {location}: {result['content'][0]['text']}"
    
    # Retorna apenas a parte em texto da resposta
    return result["content"][0]["text"]

if __name__ == "__main__":
    mcp.run(transport="stdio")  