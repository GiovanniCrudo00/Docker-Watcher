#!/usr/bin/env python3
"""
Utility per gestire il database SQLite di Docker Watcher
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'docker_stats.db')


def get_db_stats():
    """Mostra statistiche generali del database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Conta totale record
    cursor.execute('SELECT COUNT(*) FROM container_stats')
    total_records = cursor.fetchone()[0]
    
    # Conta container unici
    cursor.execute('SELECT COUNT(DISTINCT container_id) FROM container_stats')
    unique_containers = cursor.fetchone()[0]
    
    # Record più vecchio
    cursor.execute('SELECT MIN(timestamp) FROM container_stats')
    oldest_record = cursor.fetchone()[0]
    
    # Record più recente
    cursor.execute('SELECT MAX(timestamp) FROM container_stats')
    newest_record = cursor.fetchone()[0]
    
    # Dimensione del database
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)  # MB
    
    conn.close()
    
    print("=" * 60)
    print("📊 STATISTICHE DATABASE DOCKER WATCHER")
    print("=" * 60)
    print(f"📁 Path: {DB_PATH}")
    print(f"💾 Dimensione: {db_size:.2f} MB")
    print(f"📈 Totale record: {total_records:,}")
    print(f"🐳 Container unici: {unique_containers}")
    print(f"📅 Record più vecchio: {oldest_record}")
    print(f"📅 Record più recente: {newest_record}")
    print("=" * 60)


def list_containers():
    """Lista tutti i container tracciati"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT container_id, container_name, 
               COUNT(*) as record_count,
               MIN(timestamp) as first_seen,
               MAX(timestamp) as last_seen
        FROM container_stats
        GROUP BY container_id, container_name
        ORDER BY last_seen DESC
    ''')
    
    containers = cursor.fetchall()
    conn.close()
    
    print("\n🐳 CONTAINER TRACCIATI")
    print("-" * 80)
    print(f"{'ID':<15} {'Nome':<25} {'Record':<10} {'Primo':<20} {'Ultimo':<20}")
    print("-" * 80)
    
    for cont in containers:
        print(f"{cont[0]:<15} {cont[1]:<25} {cont[2]:<10} {cont[3]:<20} {cont[4]:<20}")
    
    print("-" * 80)


def cleanup_old_data(days=7):
    """Rimuove dati più vecchi di N giorni"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    limit_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Conta quanti record verranno eliminati
    cursor.execute('SELECT COUNT(*) FROM container_stats WHERE timestamp < ?', (limit_date,))
    count_to_delete = cursor.fetchone()[0]
    
    if count_to_delete == 0:
        print(f"✅ Nessun record più vecchio di {days} giorni trovato")
        conn.close()
        return
    
    print(f"⚠️  Verranno eliminati {count_to_delete:,} record più vecchi di {days} giorni")
    confirm = input("Confermi l'eliminazione? (s/n): ")
    
    if confirm.lower() == 's':
        cursor.execute('DELETE FROM container_stats WHERE timestamp < ?', (limit_date,))
        conn.commit()
        print(f"✅ Eliminati {cursor.rowcount:,} record")
        
        # Ottimizza il database
        cursor.execute('VACUUM')
        print("✅ Database ottimizzato")
    else:
        print("❌ Operazione annullata")
    
    conn.close()


def export_container_data(container_id, output_file='export.csv'):
    """Esporta i dati di un container in CSV"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT timestamp, cpu_percent, mem_usage_mb, mem_percent,
               net_input_mb, net_output_mb, disk_read_mb, disk_write_mb
        FROM container_stats
        WHERE container_id = ?
        ORDER BY timestamp ASC
    ''', (container_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print(f"❌ Nessun dato trovato per container {container_id}")
        return
    
    with open(output_file, 'w') as f:
        # Header
        f.write("timestamp,cpu_percent,mem_usage_mb,mem_percent,net_input_mb,net_output_mb,disk_read_mb,disk_write_mb\n")
        
        # Data
        for row in rows:
            f.write(','.join(map(str, row)) + '\n')
    
    print(f"✅ Esportati {len(rows):,} record in {output_file}")


def vacuum_database():
    """Ottimizza e compatta il database"""
    conn = sqlite3.connect(DB_PATH)
    
    # Dimensione prima
    size_before = os.path.getsize(DB_PATH) / (1024 * 1024)
    
    cursor = conn.cursor()
    cursor.execute('VACUUM')
    conn.commit()
    conn.close()
    
    # Dimensione dopo
    size_after = os.path.getsize(DB_PATH) / (1024 * 1024)
    saved = size_before - size_after
    
    print(f"✅ Database ottimizzato")
    print(f"📊 Prima: {size_before:.2f} MB")
    print(f"📊 Dopo: {size_after:.2f} MB")
    print(f"💾 Spazio recuperato: {saved:.2f} MB")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Uso: python db_utils.py [comando]")
        print("\nComandi disponibili:")
        print("  stats              - Mostra statistiche database")
        print("  list               - Lista container tracciati")
        print("  cleanup [giorni]   - Rimuovi dati più vecchi di N giorni (default: 7)")
        print("  export <id>        - Esporta dati container in CSV")
        print("  vacuum             - Ottimizza database")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'stats':
        get_db_stats()
    elif command == 'list':
        list_containers()
    elif command == 'cleanup':
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        cleanup_old_data(days)
    elif command == 'export':
        if len(sys.argv) < 3:
            print("❌ Specifica l'ID del container")
            sys.exit(1)
        container_id = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else f'export_{container_id}.csv'
        export_container_data(container_id, output)
    elif command == 'vacuum':
        vacuum_database()
    else:
        print(f"❌ Comando sconosciuto: {command}")
        sys.exit(1)