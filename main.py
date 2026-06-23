import os
import json
from dotenv import load_dotenv
load_dotenv()
from langchain_neo4j import Neo4jGraph, GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# =====================================================================
# LANGKAH 1: SETUP KONEKSI DATABASE & LLM OPENROUTER
# =====================================================================
print("\n=== [LANGKAH 1] Menginisialisasi Koneksi ke Neo4j & OpenRouter ===")

NEO4J_URI = "bolt://localhost:7687" 
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "raihan123" 

# API Key OpenRouter kamu
os.environ["OPENROUTER_API_KEY"] = os.getenv("OPENROUTER_API_KEY")
# Inisialisasi LLM menggunakan model gratis yang baru kamu dapatkan
llm = ChatOpenAI(
    openai_api_base="https://openrouter.ai/api/v1",
    openai_api_key=os.environ["OPENROUTER_API_KEY"],
    model_name="cohere/north-mini-code:free", # <--- GANTI BAGIAN INI
    temperature=0
)

graph = Neo4jGraph(
    url=NEO4J_URI, 
    username=NEO4J_USERNAME, 
    password=NEO4J_PASSWORD
)

print("\n[SUKSES] Koneksi Berhasil Terbentuk!")
print(graph.schema)
print("\n>>> TUGAS ANDA: Ambil SCREENSHOT 1 pada layar Terminal ini sekarang!")
input("Tekan ENTER untuk melanjutkan ke Langkah 2...")
# =====================================================================
# LANGKAH 2: LLM FOR GRAPH BUILDER (UNTUK SCREENSHOT 2)
# =====================================================================
print("\n=== [LANGKAH 2] Menjalankan LLM Graph Builder ===")

# Mengambil 50 sampel tweet mentah yang belum dianalisis dari Neo4j
query_get_tweets = "MATCH (t:Tweet) WHERE t.content IS NOT NULL RETURN id(t) AS id, t.content AS text LIMIT 50"
tweets = graph.query(query_get_tweets)

# Prompt instruksi agar LLM mengekstrak informasi terstruktur (JSON) dari teks bebas
prompt_builder = ChatPromptTemplate.from_template("""
Analisis teks tweet berikut. Ekstrak 2 hal:
1. 'sentiment': (Positif, Negatif, atau Netral)
2. 'topic': (Satu kata kunci topik utama, misalnya Politik, Agama, Rasisme, atau Umum)
Teks: {teks}
Format output wajib berupa JSON: {{"sentiment": "...", "topic": "..."}}
""")

parser = JsonOutputParser()
chain_builder = prompt_builder | llm | parser

print(f"Sedang memproses {len(tweets)} data tweet menggunakan AI untuk pengayaan entitas...")

for idx, tweet in enumerate(tweets):
    try:
        # Panggil LLM untuk mengekstrak sentimen dan topik
        hasil = chain_builder.invoke({"teks": tweet['text']})
        
        # Injeksi entitas baru hasil analisis LLM kembali ke dalam struktur Graph Neo4j
        query_insert = """
        MATCH (t:Tweet) WHERE id(t) = $tweet_id
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
        print(f"  [{idx+1}/{len(tweets)}] Sukses menambahkan relasi Topik & Sentimen: {hasil}")
    except Exception as e:
        print(f"  [{idx+1}/{len(tweets)}] Skip baris ini karena terjadi kendala: {e}")

print("\n[SUKSES] Proses LLM Graph Builder Selesai!")
print(">>> TUGAS ANDA:")
print("    1. Buka Neo4j Browser di laptop Anda.")
print("    2. Jalankan query ini: MATCH p=(:Tweet)-[]->(:Topic) RETURN p LIMIT 50")
print("    3. Ambil SCREENSHOT 2 pada visualisasi jaringan yang muncul di Neo4j Browser!")
input("Tekan ENTER jika screenshot sudah aman untuk lanjut ke Langkah 3...")


# =====================================================================
# LANGKAH 3: LLM TEXT-TO-CYPHER TRANSLATION (UNTUK SCREENSHOT 3)
# =====================================================================
print("\n=== [LANGKAH 3] Menguji Fitur Text-to-Cypher ===")

# Perbarui skema memori graph agar entitas Topic dan Sentiment baru terbaca oleh LangChain
graph.refresh_schema()

# Inisialisasi Text-to-Cypher QA Chain
cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=llm,
    qa_llm=llm,
    graph=graph,
    verbose=True,  
    return_intermediate_steps=True,
    allow_dangerous_requests=True  # <-- Tambahkan baris izin keamanan ini
)

pertanyaan = "Who are the top 5 users based on the number of tweets they posted?"
print(f"Pertanyaan Bahasa Manusia: {pertanyaan}\n")

# Eksekusi translasi query otomatis menggunakan AI
jawaban = cypher_chain.invoke({"query": pertanyaan})
print(f"\nJawaban Kontekstual dari LLM: {jawaban['result']}")
print("\n>>> TUGAS ANDA: Ambil SCREENSHOT 3 pada Terminal yang menampilkan log 'Generated Cypher'!")
input("Tekan ENTER untuk melanjutkan ke Langkah Terakhir...")


# =====================================================================
# LANGKAH 4: GRAPH-AUGMENTED RETRIEVAL / GRAPH RAG (UNTUK SCREENSHOT 4)
# =====================================================================
print("\n=== [LANGKAH 4] Mengeksekusi Analisis Menggunakan Graph RAG ===")

# Menarik subgraph relasional dari struktur data komunitas ruang gema
konteks_query = """
MATCH (u:User)-[:POSTED]->(t:Tweet)-[:DISCUSSES]->(top:Topic)
MATCH (u)-[:USES_HASHTAG]->(h:Hashtag)
WHERE h.name = 'IslamKills' OR top.name = 'Agama'
RETURN u.username AS user, collect(DISTINCT h.name) AS hashtags, count(t) AS total_tweets
ORDER BY total_tweets DESC LIMIT 10
"""
data_graf = graph.query(konteks_query)

# Prompt RAG yang memanfaatkan data topologi graf sebagai basis konteks analisis LLM
prompt_rag = ChatPromptTemplate.from_template("""
Anda adalah analis keamanan siber. Berikut adalah data hasil ekstraksi Graph Database (Neo4j) yang menunjukkan interaksi akun-akun bot di ruang gema (echo chamber) media sosial:
Konteks Data Graf:
{konteks}

Berdasarkan struktur data di atas, tolong buatkan paragraf singkat (maksimal 3 kalimat) yang menganalisis taktik kampanye ruang gema yang sedang dilakukan kelompok ini.
""")

chain_rag = prompt_rag | llm
analisis_final = chain_rag.invoke({"konteks": str(data_graf)})

print("\n=== HASIL ANALISIS GRAPH RAG KELOMPOK BOT ===")
print(analisis_final.content)
print("\n>>> TUGAS ANDA: Ambil SCREENSHOT 4 pada teks narasi analisis siber di atas!")
print("\n=== [SELESAI] Semua tahapan kode berhasil dijalankan dengan sempurna! ===")