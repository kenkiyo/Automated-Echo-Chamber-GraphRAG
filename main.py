import os
import json
import time
from dotenv import load_dotenv
load_dotenv()
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# =====================================================================
# FASE 1: INISIALISASI KONEKSI DATABASE & MODEL LLM
# =====================================================================
print("\n[INFO] Menginisialisasi koneksi ke pangkalan data Neo4j dan API OpenRouter...")

NEO4J_URI = "bolt://localhost:7687" 
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "raihan123" 

# Memuat kredensial API dari environment
os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY")

# Konfigurasi instansiasi ChatOpenAI
llm = ChatOpenAI(
    openai_api_base="https://openrouter.ai/api/v1",
    openai_api_key=os.environ["OPENROUTER_API_KEY"],
    model_name="google/gemma-4-26b-a4b-it:free",
    temperature=0
)

# Konfigurasi koneksi Neo4jGraph
graph = Neo4jGraph(
    url=NEO4J_URI, 
    username=NEO4J_USERNAME, 
    password=NEO4J_PASSWORD
)

print("[SUCCESS] Koneksi pangkalan data berhasil terbentuk.")
print(f"[INFO] Skema Graf Terkini: {graph.schema}")


# =====================================================================
# FASE 2: EKSEKUSI LLM GRAPH BUILDER PIPELINE
# =====================================================================
print("\n[INFO] Memulai eksekusi LLM Graph Builder Pipeline...")

# Ekstraksi sampel data mentah dari pangkalan data graf (menggunakan elementId untuk kompatibilitas versi terbaru)
query_get_tweets = "MATCH (t:Tweet) WHERE t.content IS NOT NULL RETURN elementId(t) AS id, t.content AS text LIMIT 50"
tweets = graph.query(query_get_tweets)

# Definisi templat prompt untuk ekstraksi entitas JSON
prompt_builder = ChatPromptTemplate.from_template("""
Analisis teks tweet berikut. Ekstrak 2 hal:
1. 'sentiment': (Positif, Negatif, atau Netral)
2. 'topic': (Satu kata kunci topik utama, misalnya Politik, Agama, Rasisme, atau Umum)
Teks: {teks}
Format output wajib berupa JSON: {{"sentiment": "...", "topic": "..."}}
""")

parser = JsonOutputParser()
chain_builder = prompt_builder | llm | parser

print(f"[PROCESS] Memproses {len(tweets)} entitas tweet untuk pengayaan data...")

for idx, tweet in enumerate(tweets):
    try:
        # Eksekusi LLM untuk pemrosesan teks
        hasil = chain_builder.invoke({"teks": tweet['text']})
        
        # Kueri Cypher untuk pembaruan topologi graf (Merge Nodes & Relationships)
        query_insert = """
        MATCH (t:Tweet) WHERE elementId(t) = $tweet_id
        MERGE (s:Sentiment {name: $sentiment})
        MERGE (topic:Topic {name: $topic})
        MERGE (t)-[:HAS_SENTIMENT]->(s)
        MERGE (t)-[:DISCUSSES]->(topic)
        """
        graph.query(query_insert, params={
            "tweet_id": tweet['id'],
            "sentiment": hasil['sentiment'],
            "topic": hasil['topic']
        })
        print(f"  -> [{idx+1}/{len(tweets)}] [SUCCESS] Entitas diekstrak & diintegrasikan: {hasil}")
        
        # Penundaan eksekusi untuk mematuhi batasan rate limit API (15 requests/minute)
        time.sleep(4.1) 
        
    except Exception as e:
        print(f"  -> [{idx+1}/{len(tweets)}] [ERROR] Kegagalan pemrosesan baris: {e}")

print("[SUCCESS] Operasi LLM Graph Builder selesai.")


# =====================================================================
# FASE 3: MESIN TRANSLASI TEXT-TO-CYPHER
# =====================================================================
print("\n[INFO] Menginisialisasi Mesin Translasi Text-to-Cypher...")

# Pembaruan skema graf pada memori LangChain
graph.refresh_schema()

# Instansiasi objek GraphCypherQAChain
cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=llm,
    qa_llm=llm,
    graph=graph,
    verbose=True,  
    return_intermediate_steps=True,
    allow_dangerous_requests=True
)

pertanyaan = "Who are the top 5 users based on the number of tweets they posted?"
print(f"[INPUT] Natural Language Query: {pertanyaan}\n")

# Pemrosesan kueri bahasa alami menjadi Cypher
jawaban = cypher_chain.invoke({"query": pertanyaan})
print(f"\n[OUTPUT] LLM Response: {jawaban['result']}")


# =====================================================================
# FASE 4: GRAPH-AUGMENTED RETRIEVAL (GRAPH RAG) ANALYTICS
# =====================================================================
print("\n[INFO] Mengeksekusi Analisis Menggunakan Graph RAG...")

# Ekstraksi subgraph dari komunitas target
konteks_query = """
MATCH (u:User)-[:POSTED]->(t:Tweet)-[:DISCUSSES]->(top:Topic)
MATCH (u)-[:USES_HASHTAG]->(h:Hashtag)
WHERE h.name = 'IslamKills' OR top.name = 'Agama'
RETURN u.username AS user, collect(DISTINCT h.name) AS hashtags, count(t) AS total_tweets
ORDER BY total_tweets DESC LIMIT 10
"""
data_graf = graph.query(konteks_query)

# Definisi prompt RAG berbasis konteks graf
prompt_rag = ChatPromptTemplate.from_template("""
Anda adalah analis keamanan siber. Berikut adalah data hasil ekstraksi Graph Database (Neo4j) yang menunjukkan interaksi akun-akun bot di ruang gema (echo chamber) media sosial:
Konteks Data Graf:
{konteks}

Berdasarkan struktur data di atas, tolong buatkan paragraf singkat (maksimal 3 kalimat) yang menganalisis taktik kampanye ruang gema yang sedang dilakukan kelompok ini.
""")

chain_rag = prompt_rag | llm
analisis_final = chain_rag.invoke({"konteks": str(data_graf)})

print("\n[RESULT] Analisis Keamanan Siber Graph RAG:")
print("-" * 60)
print(analisis_final.content)
print("-" * 60)

print("\n[INFO] Seluruh tahapan pipeline berhasil dieksekusi. Mengakhiri sistem.")