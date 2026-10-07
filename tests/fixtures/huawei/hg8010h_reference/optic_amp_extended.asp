<script>
function stOpticInfo(domain,LinkStatus,transOpticPower,revOpticPower,voltage,temperature,bias,rfRxPower,rfOutputPower,VendorName,VendorSN,DateCode,TxWaveLength,RxWaveLength,MaxTxDistance,LosStatus)
{
    this.domain = domain;
    this.LinkStatus = LinkStatus;
    this.transOpticPower = transOpticPower;
    this.revOpticPower = revOpticPower;
    this.voltage = voltage;
    this.temperature = temperature;
    this.bias = bias;
    this.rfRxPower = rfRxPower;
    this.rfOutputPower = rfOutputPower;
}
var opticInfos = new Array(
    new stOpticInfo("InternetGatewayDevice.WANDevice.1", "up", "2.16", "-19.07", "3317", "53", "7", "--", "--", "HUAWEI", "REDACTED", "000000", "1490", "1310", "20", "normal"),
    null
);
</script>
