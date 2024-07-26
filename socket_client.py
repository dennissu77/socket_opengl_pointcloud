import socket
import time
  
def read_cloud_point_file(filename):
    with open(filename, 'r') as file:
        return [line.strip().split() for line in file]

def start_client(send_delay):
    host = '127.0.0.1'
    port = 65432

    # 讀取文件並存儲為list
    data_list = read_cloud_point_file('cloud_point_with_color.asc')

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        print(f"已連接到服務器 {host}:{port}")

        # 監測變數
        start_time = time.time()
        message_count = 0
        max_messages_per_second = 0

        # 每次發送1行數據
        chunk_size = (183234)
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i:i+chunk_size]
            message = '\n'.join([' '.join(row) for row in chunk]) + '\n\n'  # 添加分隔符
            s.sendall(message.encode())
            print(f"已發送: {i+1} 到 {min(i+chunk_size, len(data_list))} 行")

            data = b''
            while b'\n\n' not in data:
                data += s.recv(2457600 )#24576     8192
            #print(f"收到回覆: {data.decode()}")

            # 更新監測數據
            message_count += 1
            elapsed_time = time.time() - start_time

            # 每秒更新一次統計信息
            if message_count % 100 == 0 or i == len(data_list) - 1:
                messages_per_second = message_count / elapsed_time
                max_messages_per_second = max(max_messages_per_second, messages_per_second)
                print(f"已經過 {elapsed_time:.2f} 秒")
                print(f"已發送 {message_count} 條訊息")
                print(f"當前每秒發送速率: {messages_per_second:.2f} 條/秒")
                print(f"最大每秒發送速率: {max_messages_per_second:.2f} 條/秒")

            # 發送延遲
            time.sleep(send_delay)

        total_time = time.time() - start_time
        overall_rate = message_count / total_time
        print("\n所有數據已發送完畢")
        print(f"總共用時: {total_time:.2f} 秒")
        print(f"總共發送: {message_count} 條訊息")
        print(f"平均每秒發送速率: {overall_rate:.2f} 條/秒")
        print(f"最大每秒發送速率: {max_messages_per_second:.2f} 條/秒")

if __name__ == "__main__":
    start_client(send_delay=0)  # 設定發送延遲為0.1秒
