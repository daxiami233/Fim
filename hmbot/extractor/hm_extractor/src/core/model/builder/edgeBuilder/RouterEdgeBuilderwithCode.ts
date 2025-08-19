import { Stmt, ArkMethod, Scene, ArkInvokeStmt } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";
import { EdgeBuilderInterface } from "./BasicEdgeBuilder";
import Utils from "../../../common/Utils";

export class RouterEdgeBuilderwithCode implements EdgeBuilderInterface{
    edgeBuilderStrategy: string = "RouterEdgeBuilderwithCode";
    scene: Scene;
    ptg:PageTransitionGraph;

    constructor(scene: Scene, ptg: PageTransitionGraph){
        this.scene = scene;
        this.ptg = ptg;
    }
    identifyPTGEdge(ptgNode: PTGNode, method: ArkMethod): void {
        const cfg = method.getBody()?.getCfg();
        for(const unit of method.getCfg()!.getStmts()) {
            this.identifyPTGEdgeByCodeMatching(ptgNode, unit);
        }
    }

    /**
     * 根据page迁移语句识别PTGEdge
     * 通过源码正则匹配的方法
     * @param ptgNode 
     * @param unit 
     */
    identifyPTGEdgeByCodeMatching(ptgNode: PTGNode, unit: Stmt) {
        // console.log("identify PTG edge by matching code");
        // 获取PTG节点的类名
        const caller = ptgNode.getClassOfPage().toString();
        let callee = "";
        // 判断语句是否为ArkInvokeStmt类型
        if(unit instanceof ArkInvokeStmt) {
            let expr = unit.getInvokeExpr();
            let invokeMethod = expr.getMethodSignature();
            const code = unit.getOriginalText();
            const invokeMethodName = invokeMethod.getMethodSubSignature().getMethodName().toString();
            // 判断调用方法名是否为pushUrl或replaceUrl
            if(invokeMethodName=='pushUrl' ||  invokeMethodName=='replaceUrl') {
                // 定义URL模式
                const urlPattern = /url:\s*['"]([^'"]+)['"]/g;
                // 获取匹配结果
                const matches = [...code!.matchAll(urlPattern)];
                // 遍历匹配结果
                for (const match of matches) {
                    // 获取目标页面名
                    let targetPageName = match[1];
                    // 获取目标页面类的签名
                    // callee = Utils.getComponentClassOfPage(this.scene, targetPageName)!.getSignature().toString();
                    this.ptg.addPTGEdgeByName(caller, callee, unit);
                }
            }
        }
    }

    
    
}