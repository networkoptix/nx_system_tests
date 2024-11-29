<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
<xsl:template match="/">
<html>
    <head>
        <link rel="stylesheet" href="/templates/services.css"/>
    </head>
    <body>
        <xsl:if test="/root/failed_hosts/item"></xsl:if>
            <h1>Failed hosts:</h1>
            <dl>
                <xsl:for-each select="/root/failed_hosts/item">
                <dt class="non-healthy"><xsl:value-of select="."/></dt>
                </xsl:for-each>
            </dl>
        <h1>FT services</h1>
        <table>
            <thead>
                <tr>
                    <th>Host</th>
                    <th>Service</th>
                    <th>State</th>
                    <th>Since</th>
                    <th>Upheld By</th>
                    <th>Info</th>
                </tr>
            </thead>
            <tbody>
            <xsl:for-each select="/root/services/item">
            <tr>
                <td><xsl:value-of select="./host"/></td>
                <td><xsl:value-of select="./id"/></td>
                <td class="{./health}"><xsl:value-of select="./state"/></td>
                <td><xsl:value-of select="./since"/></td>
                <td><xsl:value-of select="./upheld_by"/></td>
                <td>
                    <span style="display: block;"><xsl:value-of select="./ExecStart"/></span>
                    <span style="display: block;"><xsl:value-of select="./TimersCalendar"/></span>
                    <span style="display: block;"><xsl:value-of select="./Triggers"/></span>
                </td>
            </tr>
            </xsl:for-each>
            </tbody>
        </table>
    </body>
</html>
</xsl:template>
</xsl:stylesheet>
