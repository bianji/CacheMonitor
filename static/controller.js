/**
 * Created by bianji on 16/3/9.
 */
$(document).ready(function () {
        var socket = io.connect('http://' + document.domain + ':' + location.port + '/test');
        socket.on('connect', function() {
            socket.emit('event',{"data":$("#s_type").val()});
        });

        socket.on('servers', function (msg) {
            console.log(msg);
            $("#server").empty();
            $.each(msg.data,function(index,value){
                var opt = '<option value=' + value + '>' + value + '</option>';
                $("#server").append(opt)
            })
        });
        socket.on('command_result',function(msg){
            var opt = '执行结果:';
            opt += msg.data;
            $("#command_result").html(opt)
        });
        socket.on('result',function(msg){
            if (msg.server == $("#server").val()) {
                make_Echarts(msg);
                var stat_opt = '';
                $.each(msg.stat,function(key,value) {
                    stat_opt += '<tr>' + '<td style="font-weight: bold">' + key + '</td>' + '<td>' + value + '</td>' + '</tr>'
                });
                var table_opt = '';
                $.each(msg.table,function(index,value) {
                    table_opt += '<tr>';
                    $.each(value,function(k,v) {
                        table_opt += '<td>' + v + '</td>'
                    });
                    table_opt += '</tr>'
                });
                $("#table tbody").html(table_opt);
                $("#stat").html(stat_opt);
            }
        });
        $(function() {
            $('form').on('submit',function() {
                socket.emit('command',{'server':$("select").val(),
                                    'command':$("#command").val(),
                                    'args':$("#args").val()});
                return false;
            })
        });
        function MakeCommandForm(data) {
            $.each(data,function(index,value) {
                   var opt = '<option value=' + value.toLowerCase() + '>' + value + '</option>';
                   $("#command").append(opt)
               })
        }
        $("#s_type").change(function () {
           $("#command").empty();
           var server_type = $("#s_type").val();
           socket.emit('event',{'data':server_type});
           if (server_type == 'redis') {
               var head = '<tr><th>时间</th><th>用户占用CPU</th><th>系统占用CPU</th><th>客户端连接</th><th>阻塞客户端连接</th><th>内存使用</th><th>内存碎片</th><th>key总量</th><th>每秒执行</th><th>每秒过期</th><th>每秒删除</th><th>每秒命中</th><th>每秒未命中</th><th>AOF文件大小</th></tr>';
               var command_list = ["GET","HGET","HKEY","KEYS","LRANGE","LLEN"];
           }
           else {
               var head = '<tr><th>时间</th><th>get总量</th><th>set总量</th><th>命中次数</th><th>未命中次数</th><th>内存使用</th><th>打开的连接数</th><th>命中比例</th><th>内存使用比例</th></tr>';
               var command_list = ["GET","STATS"];
           }
           MakeCommandForm(command_list);
           $("thead").html(head);
        });
        var qpsecharts = echarts.init($("#qps_pic")[0]);
        function make_Echarts(data) {
            var option = {
                title : {
                    text: 'Redis服务器QPS'
                },
                tooltip : {
                    trigger: 'axis'
                },
                legend: {
                    data:['QPS']
                },
                toolbox: {
                    show : true,
                    feature : {
                        mark : {show: true},
                        dataView : {show: true, readOnly: false},
                        magicType : {show: true, type: ['line', 'bar']},
                        restore : {show: true},
                        saveAsImage : {show: true}
                    }
                },
                calculable : true,
                xAxis : [
                    {
                        type : 'category',
                        boundaryGap : false,
                        data : []
                    }
                ],
                yAxis : [
                    {
                        type : 'value',
                        axisLabel : {
                            formatter: '{value} '
                        }
                    }
                ],
                series : [
                    {
                        name:'QPS',
                        type:'line',
                        data:[],
                        markPoint : {
                            data : [
                                {type : 'max', name: '最大值'},
                                {type : 'min', name: '最小值'}
                            ]
                        },
                        markLine : {
                            data : [
                                {type : 'average', name: '平均值'}
                            ]
                        }
                    }
                ]
            };
            if (data.type == 'redis') {
                console.log('redis');
                option.title.text = 'Redis服务器QPS';
                option.yAxis[0].axisLabel.formatter = '{value} ';
                option.legend.data[0] = 'QPS';
                option.series[0].name = 'QPS';
                $.each(data.qps,function(index,value) {
                    console.log(index,value);
                    option.xAxis[0].data[index] = value.time;
                    option.series[0].data[index]= value.data;
                });
            }
            else {
                console.log('memcache');
                option.title.text = 'Memcache命中率';
                option.yAxis[0].axisLabel.formatter = '{value} %';
                option.legend.data[0] = '命中率';
                option.series[0].name = '命中率';
                $.each(data.hits,function(index,value) {
                    console.log(index,value);
                    option.xAxis[0].data[index] = value.time;
                    option.series[0].data[index]= value.data;
                });
            }
            qpsecharts.setOption(option)
        }
    });