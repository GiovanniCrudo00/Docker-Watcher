#!/usr/bin/env python3
"""
Utility for DB interactions of Docker Watcher
"""

import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), 'docker_stats.db')


def get_db_stats():
    """Get stats from Db table"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count total records
    cursor.execute('SELECT COUNT(*) FROM container_stats')
    total_records = cursor.fetchone()[0]
    
    # Count unique containers
    cursor.execute('SELECT COUNT(DISTINCT container_id) FROM container_stats')
    unique_containers = cursor.fetchone()[0]
    
    # Oldest Record
    cursor.execute('SELECT MIN(timestamp) FROM container_stats')
    oldest_record = cursor.fetchone()[0]
    
    # Latest rescord
    cursor.execute('SELECT MAX(timestamp) FROM container_stats')
    newest_record = cursor.fetchone()[0]
    
    # DB dimension
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)  # MB
    
    conn.close()
    
    print("=" * 60)
    print("📊 DB STAT FOR DOCKER WATCHER")
    print("=" * 60)
    print(f"📁 Path: {DB_PATH}")
    print(f"💾 Dimension: {db_size:.2f} MB")
    print(f"📈 Total number of records: {total_records:,}")
    print(f"🐳 Unique Containers: {unique_containers}")
    print(f"📅 oldest record: {oldest_record}")
    print(f"📅 Latest record: {newest_record}")
    print("=" * 60)


def list_containers():
    """List all traced containers"""
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
    
    print("\n🐳 TRACKED CONTAINER")
    print("-" * 80)
    print(f"{'ID':<15} {'Name':<25} {'Record':<10} {'First':<20} {'Latest':<20}")
    print("-" * 80)
    
    for cont in containers:
        print(f"{cont[0]:<15} {cont[1]:<25} {cont[2]:<10} {cont[3]:<20} {cont[4]:<20}")
    
    print("-" * 80)


def cleanup_old_data(days=7):
    """Remove containers older than N"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    limit_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    # Count removed records
    cursor.execute('SELECT COUNT(*) FROM container_stats WHERE timestamp < ?', (limit_date,))
    count_to_delete = cursor.fetchone()[0]
    
    if count_to_delete == 0:
        print(f"✅ No records olfer than {days} days found")
        conn.close()
        return
    
    print(f"⚠️  Will be removed {count_to_delete:,} records older than {days} days")
    confirm = input("Confirm removal? (y/n): ")
    
    if confirm.lower() == 'y':
        cursor.execute('DELETE FROM container_stats WHERE timestamp < ?', (limit_date,))
        conn.commit()
        print(f"✅ Removed {cursor.rowcount:,} records")
        
        # Ottimizza il database
        cursor.execute('VACUUM')
        print("✅ Optimized DB")
    else:
        print("❌ Aborted operation")
    
    conn.close()


def export_container_data(container_id, output_file='export.csv'):
    """Export data in CSV format"""
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
        print(f"❌No record found for container {container_id}")
        return
    
    with open(output_file, 'w') as f:
        # Header
        f.write("timestamp,cpu_percent,mem_usage_mb,mem_percent,net_input_mb,net_output_mb,disk_read_mb,disk_write_mb\n")
        
        # Data
        for row in rows:
            f.write(','.join(map(str, row)) + '\n')
    
    print(f"✅ Exported {len(rows):,} records in {output_file}")


def vacuum_database():
    """Optimize and reduce Db dimension"""
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
    
    print(f"✅ Optimized Database")
    print(f"📊 Before: {size_before:.2f} MB")
    print(f"📊 After: {size_after:.2f} MB")
    print(f"💾 Saved space: {saved:.2f} MB")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python db_utils.py [command]")
        print("\nAvailable commands:")
        print("  stats              - show db stats")
        print("  list               - list all traced containers")
        print("  cleanup [days]   - remove infos older than N days (default: 7)")
        print("  export <id>        - Export container data in CSV format")
        print("  vacuum             - Optimize DB")
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
            print("❌ Specify container ID")
            sys.exit(1)
        container_id = sys.argv[2]
        output = sys.argv[3] if len(sys.argv) > 3 else f'export_{container_id}.csv'
        export_container_data(container_id, output)
    elif command == 'vacuum':
        vacuum_database()
    else:
        print(f"❌ Unkown command: {command}")
        sys.exit(1)