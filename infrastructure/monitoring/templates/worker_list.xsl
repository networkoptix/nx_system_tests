<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xsl:version="1.0">
    <head>
        <link rel="stylesheet" href="/templates/workers.css"/>
    </head>
    <body>
        <h1><xsl:value-of select="root/app_name"/> workers:</h1>
        <xsl:for-each select="root/groups/item">
        <dl>
            <h2>Group "<xsl:value-of select="group_id"/>" (<a href="{tasks_url}">tasks</a>)</h2>
            <xsl:for-each select="states/item">
            <dt style="padding-bottom: 10px;">
                <p style="display: inline;"><xsl:value-of select="id"/>: </p>
                <p class="{status/class}" style="display: inline;"><xsl:value-of select="status/text"/>; </p>
                <p style="display: inline;">last seen <xsl:value-of select="seconds_since_last_update"/> seconds ago</p>
                <xsl:if test="task">
                <dd><xsl:value-of select="task/id"/></dd>
                <dd><a href="{task/artifacts/href}">Task artifacts on <xsl:value-of select="task/artifacts/url"/></a></dd>
                <dd><pre><xsl:value-of select="task/script_args"/></pre></dd>
                </xsl:if>
            </dt>
            </xsl:for-each>
        </dl>
        </xsl:for-each>
    </body>
</html>
