"""
docker 动态端口映射(dynamic port mapping)

系统要求: 带有 iptables 的 linux 系统;root 用户登录
"""

import time
import docker
import subprocess


def run_cmd(cmd):
    """
    运行系统命令并获取结果
    :param cmd:
    :return: 返回执行该命令后的标准输出和标准错误
    """

    cmd_popen = subprocess.Popen(cmd, shell=True, close_fds=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)

    result = cmd_popen.communicate()

    return_code = cmd_popen.returncode

    return return_code, result


def get_container_ip(id_or_name, network=None):
    """
    获取容器IP
    :param id_or_name:
    :param network: 容器所用的 docker 网络名，自动获取失败时请使用此参数指定 docker 网络名
    :return:
    """
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    container = client.containers.get(id_or_name)

    if network:
        network_name = network
    else:
        network_mode = container.attrs['HostConfig']['NetworkMode']

        network_name = 'bridge' if network_mode == 'default' else network_mode

    if network_name not in container.attrs['NetworkSettings']['Networks'].keys():
        raise RuntimeError(
            '此 {0} 容器找不到 {1} 网络名, 请使用 network 指定使用的网络名; 若已使用 network 参数，请确定参数是否正确(使用 docker inspect 命令可以查看)'.format(
                id_or_name, network_name))

    return container.attrs['NetworkSettings']['Networks'][network_name]['IPAddress']


def add_ports(id_or_name, ports):
    """
    添加端口映射
    :param id_or_name:
    :param ports: 要添加的端口列表，格式为 ['宿主机端口1:容器端口1', '宿主机端口2:容器端口2', ...] ; 例如: ['80:80', '443:443']
    :return:
    """
    container_ip = get_container_ip(id_or_name)

    base_cmd = 'iptables -t nat -A DOCKER -p tcp --dport {0} -j DNAT --to-destination {1}:{2}'
    add_ports_cmd = ' && '.join(list(map(
        lambda x: base_cmd.format(x.split(':')[0], container_ip, x.split(':')[1]),
        ports
    )))

    add_code, add_result = run_cmd(add_ports_cmd)

    return {
        'ok': add_code == 0,
        'msg': str(add_result[0], 'utf-8') + '\n' + str(add_result[1], 'utf-8'),
        'result': {}
    }


def del_ports(ports):
    """
    删除端口映射
    :param ports: 映射的宿主机端口
    :return:
    """
    base_cmd = 'iptables -t nat -nvL DOCKER --line-numbers | grep dpt:{0}'
    awk = " | awk -F' ' '{print $1}'"

    error_dict = {}
    for port in ports:
        get_number_cmd = base_cmd.format(port) + awk

        get_code, get_result = run_cmd(get_number_cmd)

        if get_code == 0 or get_result[0]:
            del_cmd = 'iptables -t nat -D DOCKER {0}'.format(str(get_result[0], 'utf-8').strip())
            del_code, del_result = run_cmd(del_cmd)
            if del_code != 0:
                error_dict[port] = 'iptables 规则删除失败: \n{0}\n{1}'.format(str(del_result[0], 'utf-8'),
                                                                        str(del_result[1], 'utf-8'))
        else:
            error_dict[port] = 'iptables 中没有找到此端口:\n {0}\n{1}'.format(str(get_result[0], 'utf-8'),
                                                                      str(get_result[1], 'utf-8'))

        time.sleep(0.5)

    return {
        'ok': len(error_dict.keys()) == 0,
        'msg': '端口映射规则删除成功' if len(error_dict.keys()) == 0 else '端口映射规则删除失败，详见 result ',
        'result': error_dict,
    }


if __name__ == '__main__':
    result = add_ports('docker-compose-nginx-1', ['5555:80'])
    print(result)
