<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <body>
        <h1>Welcome to <xsl:value-of select="data/app_name"/></h1>
        <xsl:for-each select="root/ui_urls/item">
        <a href="{.}" style="display: block"><xsl:value-of select="."/></a>
        </xsl:for-each>
    </body>
</html>
